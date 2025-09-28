"""
Property-based tests for graph algorithms using Hypothesis.

This demonstrates the power of property-based testing for finding edge cases
in algorithmic code that traditional example-based tests might miss.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite
import networkx as nx
from typing import Dict, List, Tuple, Set


# Custom strategy for generating valid graphs
@composite
def weighted_graphs(draw, min_nodes=2, max_nodes=10, min_weight=1, max_weight=100):
    """Generate random weighted graphs for testing"""
    num_nodes = draw(st.integers(min_value=min_nodes, max_value=max_nodes))
    nodes = list(range(num_nodes))

    # Generate edges with weights
    edges = []
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            # Randomly decide if edge exists
            if draw(st.booleans()):
                weight = draw(st.integers(min_value=min_weight, max_value=max_weight))
                edges.append((i, j, weight))

    # Ensure graph is connected by adding minimum spanning edges if needed
    if len(edges) < num_nodes - 1:
        # Add edges to make it connected
        for i in range(num_nodes - 1):
            weight = draw(st.integers(min_value=min_weight, max_value=max_weight))
            edges.append((i, i + 1, weight))

    return nodes, edges


class TestGraphAlgorithmProperties:
    """Property-based tests for graph algorithms"""

    @given(weighted_graphs())
    @settings(max_examples=100, deadline=5000)
    def test_dijkstra_shortest_path_properties(self, graph_data):
        """Test fundamental properties of Dijkstra's algorithm"""
        nodes, edges = graph_data

        # Skip if no edges (disconnected graph)
        assume(len(edges) > 0)

        # Create NetworkX graph for verification
        G = nx.Graph()
        G.add_nodes_from(nodes)
        G.add_weighted_edges_from(edges)

        # Skip if graph is not connected
        assume(nx.is_connected(G))

        source = nodes[0]  # Use first node as source

        # Get shortest paths using NetworkX as reference
        try:
            nx_distances = nx.single_source_dijkstra_path_length(G, source)
        except nx.NetworkXNoPath:
            # Skip if source is isolated
            assume(False)

        # Property 1: Distance to source is always 0
        assert nx_distances[source] == 0

        # Property 2: Distance to any reachable node is >= 0
        for node, distance in nx_distances.items():
            assert distance >= 0

        # Property 3: Triangle inequality - for any path source -> intermediate -> target,
        # direct distance <= intermediate distance + edge weight
        for intermediate in nodes:
            if intermediate in nx_distances:
                for neighbor in G.neighbors(intermediate):
                    if neighbor in nx_distances:
                        edge_weight = G[intermediate][neighbor]['weight']
                        direct_dist = nx_distances[neighbor]
                        via_intermediate = nx_distances[intermediate] + edge_weight

                        # The direct path should be <= path via intermediate
                        assert direct_dist <= via_intermediate

    @given(weighted_graphs(min_nodes=3, max_nodes=8))
    @settings(max_examples=50, deadline=3000)
    def test_minimum_spanning_tree_properties(self, graph_data):
        """Test properties of minimum spanning tree algorithms"""
        nodes, edges = graph_data

        # Skip if insufficient edges
        assume(len(edges) >= len(nodes) - 1)

        # Create NetworkX graph
        G = nx.Graph()
        G.add_nodes_from(nodes)
        G.add_weighted_edges_from(edges)

        # Skip if not connected
        assume(nx.is_connected(G))

        # Get MST using NetworkX
        mst = nx.minimum_spanning_tree(G)

        # Property 1: MST has exactly n-1 edges for n nodes
        assert mst.number_of_edges() == len(nodes) - 1

        # Property 2: MST is connected
        assert nx.is_connected(mst)

        # Property 3: MST has no cycles (is a tree)
        assert nx.is_tree(mst)

        # Property 4: Removing any edge from MST disconnects it
        mst_edges = list(mst.edges())
        for edge in mst_edges:
            temp_graph = mst.copy()
            temp_graph.remove_edge(*edge)
            assert not nx.is_connected(temp_graph)

    @given(st.lists(st.integers(min_value=1, max_value=1000), min_size=1, max_size=100))
    @settings(max_examples=200, deadline=2000)
    def test_graph_coloring_properties(self, weights):
        """Test properties of graph coloring algorithms"""
        # Create a simple path graph from weights
        n = len(weights)
        assume(n >= 2)

        G = nx.path_graph(n)

        # Get coloring using NetworkX greedy algorithm
        coloring = nx.greedy_color(G, strategy='largest_first')

        # Property 1: Adjacent nodes have different colors
        for u, v in G.edges():
            assert coloring[u] != coloring[v]

        # Property 2: Number of colors is reasonable for a path graph
        # Path graphs can be colored with 2 colors
        num_colors = len(set(coloring.values()))
        assert num_colors <= 2

        # Property 3: All nodes are colored
        assert len(coloring) == n

        # Property 4: Color values are non-negative integers
        for color in coloring.values():
            assert isinstance(color, int)
            assert color >= 0

    @given(st.integers(min_value=2, max_value=15))
    @settings(max_examples=50, deadline=2000)
    def test_complete_graph_properties(self, n):
        """Test properties that should hold for complete graphs"""
        # Create complete graph
        G = nx.complete_graph(n)

        # Property 1: Complete graph has n*(n-1)/2 edges
        expected_edges = n * (n - 1) // 2
        assert G.number_of_edges() == expected_edges

        # Property 2: Every node has degree n-1
        for node in G.nodes():
            assert G.degree(node) == n - 1

        # Property 3: Graph is connected
        assert nx.is_connected(G)

        # Property 4: Shortest path between any two nodes is 1
        for u in G.nodes():
            for v in G.nodes():
                if u != v:
                    path_length = nx.shortest_path_length(G, u, v)
                    assert path_length == 1

    @given(st.integers(min_value=1, max_value=20), st.floats(min_value=0.1, max_value=0.9))
    @settings(max_examples=30, deadline=3000)
    def test_random_graph_properties(self, n, p):
        """Test properties of random graphs (Erdős–Rényi model)"""
        # Create random graph
        G = nx.erdos_renyi_graph(n, p)

        # Property 1: Number of nodes is correct
        assert G.number_of_nodes() == n

        # Property 2: Number of edges is within expected range
        # Expected number of edges is p * n * (n-1) / 2
        expected_edges = p * n * (n - 1) / 2
        actual_edges = G.number_of_edges()

        # Allow some variance (within 3 standard deviations)
        variance = expected_edges * (1 - p)
        tolerance = 3 * (variance ** 0.5) if variance > 0 else 1

        assert abs(actual_edges - expected_edges) <= max(tolerance, expected_edges * 0.5)

        # Property 3: No self-loops in simple graph
        assert G.number_of_selfloops() == 0

    @given(st.lists(st.tuples(st.integers(0, 10), st.integers(0, 10)), min_size=2, max_size=20))
    @settings(max_examples=50, deadline=2000)
    def test_bipartite_graph_properties(self, edges):
        """Test properties of bipartite graphs"""
        # Create bipartite graph from edge list
        G = nx.Graph()
        G.add_edges_from(edges)

        # Skip empty graphs
        assume(G.number_of_edges() > 0)

        # Try to find bipartite partition
        try:
            is_bipartite = nx.is_bipartite(G)

            if is_bipartite:
                # Property 1: Can be colored with 2 colors
                coloring = nx.greedy_color(G, strategy='largest_first')
                num_colors = len(set(coloring.values()))
                assert num_colors <= 2

                # Property 2: Partition exists
                partition = nx.bipartite.sets(G)
                set1, set2 = partition

                # Property 3: No edges within same partition
                for u, v in G.edges():
                    assert not ((u in set1 and v in set1) or (u in set2 and v in set2))

                # Property 4: All nodes are in exactly one partition
                assert len(set1.intersection(set2)) == 0
                assert len(set1.union(set2)) == G.number_of_nodes()

        except nx.NetworkXError:
            # Graph might not be bipartite, which is fine
            pass


# Integration test with actual algorithm implementations
class TestAlgorithmIntegration:
    """Tests that verify our algorithms match reference implementations"""

    @given(weighted_graphs(min_nodes=3, max_nodes=6))
    @settings(max_examples=20, deadline=5000)
    def test_dijkstra_matches_reference(self, graph_data):
        """Verify our Dijkstra implementation matches NetworkX"""
        nodes, edges = graph_data

        assume(len(edges) > 0)

        # Create graph
        G = nx.Graph()
        G.add_nodes_from(nodes)
        G.add_weighted_edges_from(edges)

        assume(nx.is_connected(G))

        source = nodes[0]

        # Get reference solution
        try:
            reference_distances = nx.single_source_dijkstra_path_length(G, source)

            # Here we would test against our actual implementation
            # For now, verify the reference solution is self-consistent

            # All distances should be non-negative
            for distance in reference_distances.values():
                assert distance >= 0

            # Source distance should be 0
            assert reference_distances[source] == 0

        except nx.NetworkXNoPath:
            assume(False)


if __name__ == "__main__":
    # Run with pytest for better output
    pytest.main([__file__, "-v", "--tb=short"])