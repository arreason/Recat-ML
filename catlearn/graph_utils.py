"""
Created on Wed Mar 13 13:47:33 2019

@author: christophe_c
A library for graph utilities used in our project.
"""
from __future__ import annotations
from typing import (
    Iterable, FrozenSet, Sequence, TypeVar, Generic, Union,
    Optional, Callable, Tuple, Iterator, Type, Any)
from itertools import chain, product, repeat
from collections import abc
import random
import pickle

import numpy as np
from networkx import DiGraph, NetworkXError

NodeType = TypeVar("NodeType")
ArrowType = TypeVar("ArrowType")
AlgebraType = TypeVar("AlgebraType")


class DirectedGraph(Generic[NodeType], DiGraph, abc.MutableMapping):  # pylint: disable=unsubscriptable-object
    """
    A class to encapsulate directed graphs. Initialized from a dictionary:
    Values are iterable which must range over keys of the dictionary.
    For a key k,  v in self[k] means there is a vertex k -> v.
    Different graph composition functions are provided in order to facilitate
    the generation of examples.
    """
    def __delitem__(self, node: NodeType) -> None:
        """
        delete a node from the graph
        """
        try:
            self.remove_node(node)
        except NetworkXError:
            raise KeyError(f"{node} could not be found in graph")

    def __setitem__(
            self, node: NodeType, children: Iterable[NodeType]) -> None:
        """
        add given edge to the graph
        """
        self.add_node(node)
        for child in children:
            self.add_edge(node, child)

    @property
    def op(self) -> DirectedGraph[NodeType]:
        """
        returns the opposite graph
        """
        return self.reverse(copy=False)

    def under(self, root: NodeType) -> FrozenSet[NodeType]:
        """
        Returns the set of all nodes acessible from given root,
        (not included root itself unless there is a cycle going back to it)
        """
        # get the set of first order children
        first_children = self[root]

        # use _under function to get subsequent children
        return self._under(frozenset(first_children))

    def _under(self, roots: FrozenSet[NodeType]) -> FrozenSet[NodeType]:
        """
        Returns the sef of all nodes accessible from given roots
        (including roots themselves)
        """
        # get the set of first order children which are not roots
        first_children = frozenset(chain(*(self[root] for root in roots)))

        # if first children are among roots, return roots
        if first_children <= roots:
            return roots

        # otherwise make recursive call on roots
        return self._under(roots | first_children)

    def over(self, root: NodeType) -> FrozenSet[NodeType]:
        """
        Returns the set of all nodes from which given root can be accessed,
        (not included root itself unless there is a cycle going back to it)
        """
        return self.op.under(root)

    def subgraph(self, nodes: Iterable[NodeType]) -> DirectedGraph[NodeType]:
        """
        Extract a subgraph of current graph constituted of given nodes
        """
        nodes_set = frozenset(nodes)
        return type(self)(
            {node: set(self[node]) & nodes_set for node in nodes_set})

    def prune(self, node: NodeType) -> DirectedGraph[NodeType]:
        """
        Prune a node out of the graph, but making sure that for any subgraph
        i -> pruned_node -> j, there is a i -> j vertex added
        """
        # get parents and children of node
        parents = self.op[node]
        children = self[node]

        # delete node
        del self[node]

        # add children to all parents' children sets
        for (parent, child) in product(parents, children):
            self.add_edge(parent, child)

        return self

    def __repr__(self) -> str:
        """
        return string representation of object
        """
        return (
            f"{type(self).__name__}("
            + ", ".join(
                f"{node} > {tuple(children)}"
                for node, children in self.items())
            + ")")

    def __or__(
            self, other_graph: DirectedGraph[NodeType]
    ) -> DirectedGraph[Tuple[bool, NodeType]]:
        """
        Generates a new directed graph by making the disjoint sum
        of both graphs. Changes the nodes to:
            (False, node) for nodes from the first graph
            (True, node) for nodes from the second
        """
        remap_self = {
            (False, key): [(False, value) for value in values]
            for key, values in self.items()}
        remap_other = {
            (True, key): [(True, value) for value in values]
            for key, values in other_graph.items()}
        return type(self)({**remap_self, **remap_other})

    def __and__(
            self, other_graph: DirectedGraph[NodeType]
    ) -> DirectedGraph[Tuple[NodeType, NodeType]]:
        """
        Generates a new directed graph by making the cartesian product
        of both graphs, in the category theoretic sense of the term.
        """
        return type(self)({
            (key0, key1): list(product(value0, value1))
            for (key0, value0), (key1, value1)
            in product(self.items(), other_graph.items())})

    def __add__(
            self, other_graph: DirectedGraph[NodeType]
    ) -> DirectedGraph[Tuple[bool, NodeType]]:
        """
        Generates a new directed graph by making the directed join of both
        graphs:
            nodes are:
                (False, node) for nodes in the first graph
                (True, node) for nodes in the second graph
            edges are:
                (x, n0) -> (x, n1) for n0, n1 nodes in the same base graph
                (False, n0) -> (True, n1) for any nodes n0 and n1 in the
                    first and second graph respectively?
        """
        remap_self = {
            (False, key): (
                [(False, value) for value in values]
                + [(True, other_key) for other_key in other_graph])
            for key, values in self.items()}
        remap_other = {
            (True, key): [(True, value) for value in values]
            for key, values in other_graph.items()}
        return type(self)({**remap_self, **remap_other})

    def __matmul__(
            self,
            other_graph: DirectedGraph[NodeType]
    ) -> DirectedGraph[Tuple[NodeType, NodeType]]:
        """
        Generates a new directed graph by making the product of the graph in
        that:
            - nodes are pairs (node0, node1) of nodes of each graph
            - (s0, s1) and (t0, t1) are linked by an edge if there is an edge
            (s0, t0), or (s1, t1)
        """
        return type(self)({
            (key0, key1): list(chain(
                ((value0, key1) for value0 in self[key0]),
                ((key0, value1) for value1 in other_graph[key1])))
            for key0, key1 in product(self, other_graph)})

    def __mul__(
            self, other_graph: DirectedGraph[NodeType]
    ) -> DirectedGraph[Tuple[NodeType, NodeType]]:
        """
        Generates a new directed graph by making the directed product of both
        graphs (lexicographic order)
        """
        return type(self)({
            (key0, key1): (
                [(value0, key1) for value0 in values0]
                + [(key, value1) for key, value1 in product(self, values1)])
            for (key0, values0), (key1, values1)
            in product(self.items(), other_graph.items())})

    def remap_names(
            self, key_func: Callable[[Any], Any]
    ) -> DirectedGraph[Any]:
        """
        Remap the graph nodes to new names using a function key_func to
        generate the new names.
        Be careful that the function is 1-to-1 if you want to make sure you
        do not lose certain properties of the graph, such as being acyclic
        """
        return type(self)({
            key_func(key): [key_func(value) for value in values]
            for key, values in self.items()})

    def integerify(self) -> DirectedGraph[int]:
        """
        Remap the graph nodes to integers, starting from 0 in the order of
        access in the underlying dictionary
        """
        # create a dictionary which will be used to create the mapping
        sorted_nodes = enumerate(sorted(self, key=pickle.dumps))
        remapping = {node: index for index, node in sorted_nodes}
        return self.remap_names(remapping.get)

    def stringify(self) -> DirectedGraph[str]:
        """
        Remap the graph nodes to strings generated from the
        hash code of each key
        """
        return self.integerify().remap_names(hex)

    def rand_prune(
            self, pruning_factor: float,
            random_generator: Optional[random.Random] = None
    ) -> DirectedGraph[NodeType]:
        """
        Randomly prune nodes out of the graph. The number of nodes pruned out
        of the graph is floor(pruning_factor * len(self)),
        chosen without replacement
        """
        assert 0 <= pruning_factor <= 1, (
            "pruning_factor should be a number between 0. and 1.")
        nb_to_prune = int(np.floor(pruning_factor * len(self)))

        # draw nodes to be pruned
        if random_generator is None:
            to_prune = random.sample(
                list(self), k=nb_to_prune)  # type: ignore
        else:
            to_prune = random_generator.sample(
                list(self), k=nb_to_prune)  # type: ignore

        # prune nodes
        for node in to_prune:
            self.prune(node)

        return self


class DirectedAcyclicGraph(DirectedGraph[NodeType]):
    """
        A class to model general directed acyclic graphs
    """
    def __init__(self, *args, **kwargs) -> None:
        """
            Create an acyclic directed graph from a dictinary.
        """

        # init self as directed graph
        super().__init__(*args, **kwargs)

        # check that it is indeed a directed acyclic graph
        assert all(node not in self.under(node) for node in self), (
            "A directed acyclic graph cannot contain cycles")

    @property
    def ins(self) -> FrozenSet[NodeType]:
        """
        roots of the graph
        """
        return frozenset(node for node in self if not self.op[node])

    @property
    def outs(self) -> FrozenSet[NodeType]:
        """
        roots of the opposite graph
        """
        return frozenset(node for node in self if not self[node])

    def __setitem__(self, node: NodeType, children: Iterable[NodeType]):
        """
        item setting is forbidden in a DirectedAcyclicGraph. Go through
        a DirectedGraph representation if you need to do this, then recreate
        a DirectedAcyclicGraph out of it
        """
        raise NotImplementedError(
            "item setting is not supported by DirectedAcyclicGraph objects")


class GraphRandomFactory:
    """
    A class for factories for random graph generation.
    Arguments to the constructor are:
        weights: a sequence of 5 floating point numbers, whose sum
            is less than 1, for the weights of choosing respectively the
            or, and, add, mul, matmul
        nb_graphs: the number of graphs kept into memory by the generator
        pruning_factor: the max pruning factor for the eroding operation.
            The eroding operation is chosen whenever no other operation is
            chosen, and randomly prunes a number of points of one of the graphs
        random_generator: random.Random, the random generator to use
        *initial_graphs: DirectedGraph objects, seeds to initialize the random
            generation (at most nb_graphs). If not provided, a default seed
            point graph will be used.
    """
    OPS: Tuple[Callable[..., DirectedGraph], ...] = (
        DirectedGraph.__or__,
        DirectedGraph.__and__,
        DirectedGraph.__add__,
        DirectedGraph.__mul__,
        DirectedGraph.__matmul__)
    OPS_NARGS = (2, 2, 2, 2, 2)

    DEFAULT_SEED_GRAPH = DirectedGraph[str]({"0x0": []}).stringify()

    @classmethod
    def __init_subclass__(cls: Type) -> None:
        """
        Verify that the defined OPS and OPS_NARGS are tuples of same length
        """
        assert isinstance(cls.OPS, tuple), "OPS should be a tuple"
        assert isinstance(cls.OPS_NARGS, tuple), "OPS_NARGS should be a tuple"
        assert len(cls.OPS) == len(cls.OPS_NARGS), (
            "OPS and OPS_NARGS should have the same length")

    def __init__(
            self, weights: Sequence[float], nb_graphs: int,
            pruning_factor: float,
            random_generator: random.Random,
            *initial_graphs: DirectedGraph[Any]) -> None:
        """
        create a new factory
        """
        assert 0. <= pruning_factor <= 1., (
            "pruning factor should be between 0. and 1.")
        assert len(weights) == len(__class__.OPS), (  # type: ignore
            "Weights sequence should be of length 4, for or, and, add, mul"
            "operations respectively")
        assert 0 <= len(initial_graphs) <= nb_graphs, (
            "number of initializer "
            "graphs should be at most nb_graphs: {nb_graphs}")
        assert all(weight >= 0. for weight in weights), (
            "weights should be positive")
        assert sum(weights) <= 1, "Weights should sum to less to 1."

        self._pruning_factor = pruning_factor
        self._weights = np.array(tuple(weights) + (1. - sum(weights),))
        self._nb_graphs = nb_graphs
        self._random_generator = random_generator
        self._ops = type(self).OPS + (self.erode,)
        self._ops_nargs = type(self).OPS_NARGS + (1,)

        self._graphs: Tuple[DirectedGraph, ...]
        if initial_graphs:
            self._graphs = tuple(graph.stringify() for graph in initial_graphs)
        else:
            self._graphs = (type(self).DEFAULT_SEED_GRAPH,)

    def erode(self, graph: DirectedGraph) -> DirectedGraph:
        """
        Erode the given graph by pruning it of a factor of at most the
        pruning_factor of the factory.
        """
        # get a random pruning factor between 0. and actual pruning_factor
        pruning_factor = self._random_generator.uniform(
            0., self._pruning_factor)
        return graph.rand_prune(pruning_factor)

    @property
    def nb_graphs(self) -> int:
        """
        Number of graphs held in memory by the factory
        """
        return self._nb_graphs

    @property
    def graphs(self) -> Tuple[DirectedGraph, ...]:
        """
        tuple containing the graphs held in the memory of the factory
        """
        return self._graphs

    @property
    def weights(self) -> np.ndarray:
        """
        weights of or, and, add, mul operations for the factory
        """
        return self._weights

    @property
    def ops(self) -> Tuple[Callable[..., DirectedGraph], ...]:
        """
        return list of operations of the factory
        """
        return self._ops

    @property
    def ops_nargs(self) -> Tuple[int, ...]:
        """
        number of arguments of each operand
        """
        return self._ops_nargs

    def __next__(self) -> Tuple[DirectedGraph, ...]:
        """
        generate next step graphs from current ones
        """
        # draw operations to apply for each new graph
        ops = self._random_generator.choices(
            list(enumerate(self.ops)), weights=self.weights,
            k=self.nb_graphs)

        # number of operands for each operation
        ops_nargs = [self.ops_nargs[index] for index, _ in ops]

        # choose wether the operands are taken as direct or opposite
        operands_variance = (
            self._random_generator.choices([False, True], k=op_nargs)
            for op_nargs in ops_nargs)

        # get operands for each operation, with their right variance
        operands = (
            map(
                lambda graph, var: graph if var else graph.op,
                self._random_generator.choices(self.graphs, k=op_nargs),
                ops_vars)
            for op_nargs, ops_vars in zip(ops_nargs, operands_variance))

        # generate new graphs
        self._graphs = tuple(
            op(*args).stringify()
            for (_, op), args in zip(ops, operands))

        return self._graphs


class CompositeArrow(Generic[NodeType, ArrowType], abc.Sequence):
    """
    A class for composite arrows in a graph. To initialize such a composite,
    one should provide:
        - nodes: Iterable[NodeType], the nodes of the composite in order
        - arrows: Iterable[ArrowType], the arrow labels of the composite in
            order
            Number of nodes should be 1 more than number of arrows
    """
    @property
    def nodes(self) -> Tuple[NodeType]:
        """
        Get the nodes supporting the composite as a tuple
        """
        return self._nodes

    @property
    def arrows(self) -> Tuple[ArrowType]:
        """
        Get the arrow labels of the composite as a tuple
        """
        return self._arrows

    def __new__(
            cls, nodes: Union[NodeType, Iterable[NodeType]],
            arrows: Optional[Iterable[ArrowType]]
            ) -> CompositeArrow[NodeType, ArrowType]:
        """
        Instanciate a new composite arrow from nodes and arrow labels data
        """
        self = super().__new__(cls)

        # if no arrows are given, the first argument is assumed
        # to be a unique node
        if not arrows:
            self._nodes = (nodes,)
            self._arrows = ()
        else:
            self._nodes = tuple(nodes)
            self._arrows = tuple(arrows)

        return self

    def __init__(
            self,
            nodes: Iterable[NodeType], arrows: Iterable[NodeType]) -> None:
        """
        Initialize the new composite: verify that the length of the nodes
        sequence is 1 + the length of the arrows sequence
        """
        assert len(self.nodes) == len(self.arrows) + 1

    def __getitem__(self, index: Union[int, slice]) -> NamedTuple:
        """
        Access nodes and subcomposites.
            - Accessing an integer index will access the node at the given
                index
            - Accessing a slice without step ([i:j]) will give the subarrow
                containing the elementary arrows from i-th included to
                j-th excluded
        """
        if isinstance(index, int):
            return self.nodes[index]
        elif isinstance(index, slice):
            # compute start and stop of nodes slice select nodes
            length = len(self)
            if index.start is None:
                start = 0
            elif index.start < 0:
                start = index.start + length
            else:
                start = index.start

            if index.stop is None:
                stop = 1 + length
            elif index.stop < 0:
                stop = index.stop + length + 1
            else:
                stop = index.stop + 1

            nodes_slice = slice(start, stop, index.step)
            nodes = self.nodes[nodes_slice]

            if index.step is None:
                arrows_slice = slice(start, stop - 1)
                arrows = self.arrows[arrows_slice]
                return CompositeArrow(nodes, arrows)
            else:
                arrows = (
                    self[nodes[idx]:nodes[1 + idx]]
                    for idx in range(len(nodes) - 1))
                return CompositeArrow(nodes, arrows)

    def __len__(self) -> int:
        """
        Length of the composites: number of elementary arrows of which it
        is a composite
        """
        return len(self.arrows)

    def __eq__(self, arrow: CompositeArrow[NodeType, ArrowType]) -> int:
        """
        test wether two composite arrows are equals, i.e:
            - they have the same nodes in the same order
            - they have the same arrows in the same order
        """
        return self.nodes == arrow.nodes and self.arrows == arrow.arrows

    def __add__(
            self, arrow: CompositeArrow[NodeType, ArrowType]
            ) ->  CompositeArrow[NodeType, ArrowType]:
        """
        compose 2 arrows together. The last node of the first must be the same
        as the first node of the second.
        """
        assert self[-1] == arrow[0]
        nodes = self.nodes + arrow.nodes[1:]
        arrows = self.arrows + arrow.arrows
        return CompositeArrow(nodes, arrows)

    def __matmul__(
            self, arrow: CompositeArrow[NodeType, ArrowType]
            ) -> CompositeArrow[NodeType, ArrowType]:
        """
        extend 2 composites which match on:
            - the first composite with its first arrow removed
            - the second composite with its last arrow removed
        """
        assert self[1:] == arrow[:-1]
        return self + arrow[-1:]

    def __hash__(self) -> int:
        """
        Hash code of a composite comp is computed from the hash code of
        (comp.nodes, comp.arrows)
        """
        return hash((self.nodes, self.arrows))

    def __repr__(self) -> str:
        """
        String representation of a composite arrow
        """
        return (
            f"CompositeArrow({self[0]}"
            + "".join(
                f"->{arrow}>{node}"
                for (arrow, node) in zip(self.arrows, self.nodes[1:]))) + ")"


class CompositionGraph(Generic[NodeType, ArrowType, AlgebraType], abc.Set):
    """
    Make a composition graph out of a list of Composite arrows
    """
    def __init__(
            self,
            generator: Callable[[NodeType, NodeType, ArrowType], AlgebraType],
            comp: Callable[[CompositeArrow], AlgebraType],
            *arrows: CompositeArrow[NodeType, ArrowType]):
        """
        initialize a new composition graph.
        Arguments:
            - generator: a callable which generates the value of a relation
            from the nodes and arrow indices
            - comp: a callable which computes the composite of 2 arrow values
        """
        super().__init__()
        self._graph = DirectedGraph()
        self._generator = generator
        self._comp = comp

        for arrow in arrows:
            self.add(arrow)

    def graph(self):
        return self._graph

    def add(self, arrow: CompositeArrow) -> None:
        """
        Add the given composite arrow to the composition graph
        """
        if len(arrow) == 0:
            raise ValueError("Can only add arrows of length at least 1")

        # if the arrow is already in the structure, we can stop there
        if arrow in self:
            return

        # the case of length 1 arrows is simple: generate the value
        # and put it in the graph
        if len(arrow) == 1:
            self.graph.add_edge(arrow[0], arrow[-1])
            self.graph[arrow[0]][arrow[-1]][arrow] = self._generator(
                arrow[0], arrow[1], arrow.arrows[0])
        else:
            # the case of higher order arrows is recursively defined:
            # all subcomposites of the arrow should be in the graph, so we have
            # to make the computation for all of them
            for idx in range(1, len(arrow)):

                # add the subarrows in the structure if needed
                fst_arrow = arrow[:idx]
                scd_arrow = arrow[idx:]
                if fst_arrow not in self:
                    self.add(fst_arrow)
                if scd_arrow not in self:
                    self.add(scd_arrow)
            else:
                # compute the value of the total arrow and register it
                value = self._comp(arrow)
                self._graph[arrow[0]][arrow[-1]][arrow] = value

    def flush(self) -> None:
        """
        Reset the structure, removing all composite arrows
        """
        self._graph = DirectedGraph()

    def __iter__(self) -> Iterator[CompositeArrow]:
        """
        return an iterator over all composite arrows of the structure
        """
        return iter(self.graph)

    def __len__(self) -> int:
        """
        return the number of composite arrows in the structure
        """
        return len(self.graph)

    def __getitem__(
            self, arrow: CompositeArrow[NodeType, ArrowType]) -> AlgebraType:
        """
        get value associated to given arrow
        """
        return self.graph[arrow[0]][arrow[-1]][arrow]
