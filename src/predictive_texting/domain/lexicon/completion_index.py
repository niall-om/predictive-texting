from __future__ import annotations

from collections.abc import Iterator

from ...exceptions.domain import CompletionIndexError
from ..encoding.key_space import IndexKeySpace
from ..encoding.types import EncodedIndexKeySequence
from ..lexicon.types import WordId
from ..ranking.protocols import RankingPolicy
from .protocols import RankedCompletionIndexProtocol


class _TrieNode:
    __slots__ = (
        '_parent',
        '_child_index',
        '_children',
        '_word_ids',
        '_top_k',
    )
    _parent: _TrieNode | None
    _child_index: int | None
    _children: list[_TrieNode | None]
    _word_ids: set[WordId]  # stores WordId objects; see class-level design note
    _top_k: list[WordId]

    def __init__(self, keyspace_size: int, parent: _TrieNode | None = None, child_index: int | None = None) -> None:
        self._parent = parent
        self._child_index = child_index
        self._children = [None] * keyspace_size
        self._word_ids = set()
        self._top_k = []


class RankedCompletionIndex(RankedCompletionIndexProtocol):
    """
    Implements a ranked completion index over a set of Word IDs.

    Design Note:
    WordId objects are currently stored directly in trie nodes (e.g. in `_word_ids`
    and `_top_k`). This keeps the implementation aligned with domain types and
    simplifies interfaces.

    However, this has a higher memory overhead compared to storing primitive
    identifiers (e.g. raw integers). If memory usage becomes a concern, this class
    could be optimized to store raw identifiers internally and convert to/from
    `WordId` at the boundaries.

    Such an optimization would remain an internal implementation detail and would
    not affect the public interface.
    """

    __slots__ = ('_root', '_ranking_policy', '_keyspace', '_default_k', '_node_count', '_word_count')
    _root: _TrieNode
    _ranking_policy: RankingPolicy
    _keyspace: IndexKeySpace
    _default_k: int
    _node_count: int
    _word_count: int

    def __init__(self, keyspace: IndexKeySpace, ranking_policy: RankingPolicy, k: int) -> None:
        if k <= 0:
            raise ValueError(f'k must be an integer value >= 1; got {k!r}')
        self._default_k = k
        self._keyspace = keyspace
        self._root = self._make_node(parent=None, child_index=None)
        self._ranking_policy = ranking_policy
        self._node_count = 1
        self._word_count = 0

    @property
    def k(self) -> int:
        return self._default_k

    @property
    def word_count(self) -> int:
        return self._word_count

    @property
    def node_count(self) -> int:
        return self._node_count

    def insert(self, word_id: WordId, sequence: EncodedIndexKeySequence) -> None:
        """
        Insert a word into the completion index.

        Raises CompletionIndexError if:
        - sequence is not valid (not consistent with keyspace of the index).
        - word_id is already stored in the index.

        Note:
        This associates the given word_id with the provided encoded key sequence
        and updates all relevant index structures (e.g. trie nodes and ranking summaries)
        along the path defined by the sequence.

        This method is used during:
        - initial index construction (bootstrapping)
        - insertion of newly learned words
        """
        self._validate_sequence(sequence)
        self._insert(word_id, sequence)

    def delete(self, word_id: WordId, sequence: EncodedIndexKeySequence) -> bool:
        """
        Delete a word ID from the completion index.

        Returns True if the word ID is present in the index and is deleted.
        Returns False if the word ID is not present in the index.

        Raises CompletionIndexError if:
        - sequence is not valid (not consistent with keyspace of the index).
        - sequence is not stored in the index.
        """
        self._validate_sequence(sequence)
        return self._delete(word_id, sequence)

    def get_ranked_candidates(self, sequence: EncodedIndexKeySequence) -> list[WordId]:
        """
        Return the top-K ranked candidate word IDs for the given encoded key sequence;
        where K is defined by the index at construction time.

        If the sequence does not exist in the index, an empty list is returned.

        Raises CompletionIndexError if:
        - sequence is not valid (not consistent with keyspace of the index).

        Note:
        The sequence defines a position in the index (e.g. a node in a trie).
        The method returns up to k word IDs corresponding to words whose encoded
        sequences share the same prefix, ordered according to the index's ranking policy.
        """
        self._validate_sequence(sequence)
        return self._get_ranked_candidates(sequence)

    def refresh_index(self, sequence: EncodedIndexKeySequence) -> None:
        """
        Recompute cached ranking summaries along the path defined by the given encoded key sequence.

        Raises CompletionIndexError if:
        - sequence is not valid (not consistent with keyspace of the index).
        - sequence is not stored in the index.

        Note:
        This should be called when ranking-relevant metadata for one or more words associated
        with the sequence has changed (for example, word frequency in the WordStore).
        """

        self._validate_sequence(sequence)
        self._refresh_index(sequence)

    def clear(self) -> None:
        """Clear current runtime state."""
        # rely on garbage collection to tidy up old Trie nodes
        self._root = self._make_node(parent=None, child_index=None)
        self._node_count = 1
        self._word_count = 0

    # ----------------- Internal helpers --------------------
    def _validate_sequence(self, sequence: EncodedIndexKeySequence) -> None:
        """
        Internal validation helper.

        Validate sequence against the keyspace over which this index is defined.
        Ensures data structure remains self-consistent internally and does not
        rely on callers passing valid key sequences
        """
        for key in sequence:
            if key not in self._keyspace:
                raise CompletionIndexError(f'Invalid key in sequence: {key!r}')

    def _make_node(self, parent: _TrieNode | None = None, child_index: int | None = None) -> _TrieNode:
        return _TrieNode(self._keyspace.size(), parent, child_index)

    def _find_node(self, sequence: EncodedIndexKeySequence) -> _TrieNode | None:
        node = self._root
        for key in sequence:
            index = self._keyspace.index(key)
            child = node._children[index]
            if child is None:
                return None
            node = child
        return node

    def _children(self, node: _TrieNode) -> Iterator[_TrieNode]:
        for child in node._children:
            if child is not None:
                yield child

    def _has_children(self, node: _TrieNode) -> bool:
        return any(node._children)

    def _recompute_path_ranking_and_prune(self, starting_node: _TrieNode) -> None:
        """
        Recompute top_k rankings on nodes along the path from the starting node
        up to and including the root of the trie.

        If a node is prunable after reranking (has no children, stores no word_ids) then prune it.
        """
        node: _TrieNode | None = starting_node
        while node is not None:
            self._recompute_node_ranking(node)
            parent = node._parent
            if self._is_prunable(node):
                self._prune_node(node)

            node = parent

    def _recompute_node_ranking(self, node: _TrieNode) -> None:
        """
        Recomputes the top-k word ID ranking on a node.

        Candidates word IDs for top-k at a node include
        any word IDs stored on the node itself (if the node is terminal)
        plus the top-k candidates of all nodes in the subtree rooted at `node`.

        """
        candidates: set[WordId] = set()
        candidates.update(node._word_ids)

        for child in self._children(node):
            candidates.update(child._top_k)

        node._top_k = self._ranking_policy.rank(candidates, self._default_k)

    def _is_prunable(self, node: _TrieNode) -> bool:
        return node is not self._root and not self._has_children(node) and not node._word_ids

    def _prune_node(self, node: _TrieNode) -> None:
        if not self._is_prunable(node):
            return

        parent = node._parent
        child_index = node._child_index
        assert parent is not None
        assert child_index is not None

        parent._children[child_index] = None  # delete reference but preserve keyspace on parent node
        self._node_count -= 1

    def _insert(self, word_id: WordId, sequence: EncodedIndexKeySequence) -> None:
        node = self._root

        for key in sequence:
            index = self._keyspace.index(key)
            child: _TrieNode | None = node._children[index]

            # construct missing nodes on the way down
            if child is None:
                child = self._make_node(parent=node, child_index=index)
                node._children[index] = child
                self._node_count += 1
            node = child

        if word_id in node._word_ids:
            raise CompletionIndexError(f'WordId {word_id!r} is already indexed for sequence {sequence!r}')

        node._word_ids.add(word_id)
        self._word_count += 1
        self._recompute_path_ranking_and_prune(node)

    def _delete(self, word_id: WordId, sequence: EncodedIndexKeySequence) -> bool:
        node = self._find_node(sequence)
        if node is None:
            raise CompletionIndexError('sequence is not stored in the index')

        if word_id in node._word_ids:
            node._word_ids.remove(word_id)
            self._word_count -= 1
            self._recompute_path_ranking_and_prune(node)
            return True

        return False

    def _get_ranked_candidates(self, sequence: EncodedIndexKeySequence) -> list[WordId]:
        node = self._find_node(sequence)
        return list(node._top_k) if node is not None else []

    def _refresh_index(self, sequence: EncodedIndexKeySequence) -> None:
        node = self._find_node(sequence)
        if node is None:
            raise CompletionIndexError('sequence is not stored in the index')
        self._recompute_path_ranking_and_prune(node)
