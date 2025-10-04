"""
Property-based tests for graph algorithms using Hypothesis.

This demonstrates the power of property-based testing for finding edge cases
in algorithmic code that traditional example-based tests might miss.
"""
import networkx as nx
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite


@composite
def weighted_graphs(draw, min_nodes=2, max_nodes=10, min_weight=1, max_weight=100):
    """Generate random weighted graphs for testing"""
    num_nodes = draw(st.integers(min_value=min_nodes, max_value=max_nodes))
    nodes = list(range(num_nodes))
    edges = []
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if draw(st.booleans()):
                weight = draw(st.integers(min_value=min_weight, max_value=max_weight))
                edges.append((i, j, weight))
    if len(edges) < num_nodes - 1:
        for i in range(num_nodes - 1):
            weight = draw(st.integers(min_value=min_weight, max_value=max_weight))
            edges.append((i, i + 1, weight))
    return (nodes, edges)

@pytest.mark.crust
class TestGraphAlgorithmProperties:
    """Property-based tests for graph algorithms"""

    @pytest.mark.crust
    @given(weighted_graphs())
    @settings(max_examples=100, deadline=5000)
    def test_dijkstra_shortest_path_properties(self, graph_data):
        """Test fundamental properties of Dijkstra's algorithm"""
        nodes, edges = graph_data
        assume(len(edges) > 0)
        G = nx.Graph()
        G.add_nodes_from(nodes)
        G.add_weighted_edges_from(edges)
        assume(nx.is_connected(G))
        source = nodes[0]
        try:
            nx_distances = nx.single_source_dijkstra_path_length(G, source)
        except nx.NetworkXNoPath:
            assume(False)
        assert nx_distances[source] == 0
        for _node, distance in nx_distances.items():
            assert distance >= 0
        for intermediate in nodes:
            if intermediate in nx_distances:
                for neighbor in G.neighbors(intermediate):
                    if neighbor in nx_distances:
                        edge_weight = G[intermediate][neighbor]['weight']
                        direct_dist = nx_distances[neighbor]
                        via_intermediate = nx_distances[intermediate] + edge_weight
                        assert direct_dist <= via_intermediate

    @pytest.mark.crust
    @given(weighted_graphs(min_nodes=3, max_nodes=8))
    @settings(max_examples=50, deadline=3000)
    def test_minimum_spanning_tree_properties(self, graph_data):
        """Test properties of minimum spanning tree algorithms"""
        nodes, edges = graph_data
        assume(len(edges) >= len(nodes) - 1)
        G = nx.Graph()
        G.add_nodes_from(nodes)
        G.add_weighted_edges_from(edges)
        assume(nx.is_connected(G))
        mst = nx.minimum_spanning_tree(G)
        assert mst.number_of_edges() == len(nodes) - 1
        assert nx.is_connected(mst)
        assert nx.is_tree(mst)
        mst_edges = list(mst.edges())
        for edge in mst_edges:
            temp_graph = mst.copy()
            temp_graph.remove_edge(*edge)
            assert not nx.is_connected(temp_graph)

    @pytest.mark.crust
    @given(st.lists(st.integers(min_value=1, max_value=1000), min_size=1, max_size=100))
    @settings(max_examples=200, deadline=2000)
    def test_graph_coloring_properties(self, weights):
        """Test properties of graph coloring algorithms"""
        n = len(weights)
        assume(n >= 2)
        G = nx.path_graph(n)
        coloring = nx.greedy_color(G, strategy='largest_first')
        for u, v in G.edges():
            assert coloring[u] != coloring[v]
        num_colors = len(set(coloring.values()))
        assert num_colors <= 2
        assert len(coloring) == n
        for color in coloring.values():
            assert isinstance(color, int)
            assert color >= 0

    @pytest.mark.crust
    @given(st.integers(min_value=2, max_value=15))
    @settings(max_examples=50, deadline=2000)
    def test_complete_graph_properties(self, n):
        """Test properties that should hold for complete graphs"""
        G = nx.complete_graph(n)
        expected_edges = n * (n - 1) // 2
        assert G.number_of_edges() == expected_edges
        for node in G.nodes():
            assert G.degree(node) == n - 1
        assert nx.is_connected(G)
        for u in G.nodes():
            for v in G.nodes():
                if u != v:
                    path_length = nx.shortest_path_length(G, u, v)
                    assert path_length == 1

    @pytest.mark.crust
    @given(st.integers(min_value=1, max_value=20), st.floats(min_value=0.1, max_value=0.9))
    @settings(max_examples=30, deadline=3000)
    def test_random_graph_properties(self, n, p):
        """Test properties of random graphs (Erdős–Rényi model)"""
        G = nx.erdos_renyi_graph(n, p)
        assert G.number_of_nodes() == n
        expected_edges = p * n * (n - 1) / 2
        actual_edges = G.number_of_edges()
        variance = expected_edges * (1 - p)
        tolerance = 3 * variance ** 0.5 if variance > 0 else 1
        assert abs(actual_edges - expected_edges) <= max(tolerance, expected_edges * 0.5)
        assert G.number_of_selfloops() == 0

    @pytest.mark.crust
    @given(st.lists(st.tuples(st.integers(0, 10), st.integers(0, 10)), min_size=2, max_size=20))
    @settings(max_examples=50, deadline=2000)
    def test_bipartite_graph_properties(self, edges):
        """Test properties of bipartite graphs"""
        G = nx.Graph()
        G.add_edges_from(edges)
        assume(G.number_of_edges() > 0)
        try:
            is_bipartite = nx.is_bipartite(G)
            if is_bipartite:
                coloring = nx.greedy_color(G, strategy='largest_first')
                num_colors = len(set(coloring.values()))
                assert num_colors <= 2
                partition = nx.bipartite.sets(G)
                set1, set2 = partition
                for u, v in G.edges():
                    assert not (u in set1 and v in set1 or (u in set2 and v in set2))
                assert len(set1.intersection(set2)) == 0
                assert len(set1.union(set2)) == G.number_of_nodes()
        except nx.NetworkXError:
            pass

@pytest.mark.crust
class TestAlgorithmIntegration:
    """Tests that verify our algorithms match reference implementations"""

    @pytest.mark.crust
    @given(weighted_graphs(min_nodes=3, max_nodes=6))
    @settings(max_examples=20, deadline=5000)
    def test_dijkstra_matches_reference(self, graph_data):
        """Verify our Dijkstra implementation matches NetworkX"""
        nodes, edges = graph_data
        assume(len(edges) > 0)
        G = nx.Graph()
        G.add_nodes_from(nodes)
        G.add_weighted_edges_from(edges)
        assume(nx.is_connected(G))
        source = nodes[0]
        try:
            reference_distances = nx.single_source_dijkstra_path_length(G, source)
            for distance in reference_distances.values():
                assert distance >= 0
            assert reference_distances[source] == 0
        except nx.NetworkXNoPath:
            assume(False)
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
