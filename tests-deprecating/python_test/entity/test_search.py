import time
import pdb
import copy
import logging
from multiprocessing import Pool, Process
import pytest
import numpy as np

from pymilvus import DataType
from utils import *
from constants import *

uid = "test_search"
nq = 1
epsilon = 0.001
field_name = default_float_vec_field_name
binary_field_name = default_binary_vec_field_name
search_param = {"nprobe": 1}

entity = gen_entities(1, is_normal=True)
entities = gen_entities(default_nb, is_normal=True)
raw_vectors, binary_entities = gen_binary_entities(default_nb)
default_query, default_query_vecs = gen_query_vectors(field_name, entities, default_top_k, nq)
default_binary_query, default_binary_query_vecs = gen_query_vectors(binary_field_name, binary_entities, default_top_k,
                                                                    nq)


def init_data(connect, collection, nb=3000, partition_names=None, auto_id=True):
    '''
    Generate entities and add it in collection
    '''
    global entities
    if nb == 3000:
        insert_entities = entities
    else:
        insert_entities = gen_entities(nb, is_normal=True)
    if partition_names is None:
        ids = connect.insert(collection, insert_entities)
    else:
        ids = connect.insert(collection, insert_entities, partition_name=partition_names)
    connect.flush([collection])
    return insert_entities, ids


def init_binary_data(connect, collection, nb=3000, insert=True, partition_names=None):
    '''
    Generate entities and add it in collection
    '''
    ids = []
    global binary_entities
    global raw_vectors
    if nb == 3000:
        insert_entities = binary_entities
        insert_raw_vectors = raw_vectors
    else:
        insert_raw_vectors, insert_entities = gen_binary_entities(nb)
    if insert is True:
        if partition_names is None:
            ids = connect.insert(collection, insert_entities)
        else:
            ids = connect.insert(collection, insert_entities, partition_name=partition_names)
        connect.flush([collection])
    return insert_raw_vectors, insert_entities, ids


class TestSearchBase:
    """
    generate valid create_index params
    """

    @pytest.fixture(
        scope="function",
        params=gen_index()
    )
    def get_index(self, request, connect):
        # if str(connect._cmd("mode")) == "CPU":
        #     if request.param["index_type"] in index_cpu_not_support():
        #         pytest.skip("sq8h not support in CPU mode")
        return request.param

    @pytest.fixture(
        scope="function",
        params=gen_simple_index()
    )
    def get_simple_index(self, request, connect):
        # if str(connect._cmd("mode")) == "CPU":
        #     if request.param["index_type"] in index_cpu_not_support():
        #         pytest.skip("sq8h not support in CPU mode")
        return copy.deepcopy(request.param)

    @pytest.fixture(
        scope="function",
        params=gen_binary_index()
    )
    def get_jaccard_index(self, request, connect):
        logging.getLogger().info(request.param)
        if request.param["index_type"] in binary_support():
            return request.param
        # else:
        #     pytest.skip("Skip index Temporary")

    @pytest.fixture(
        scope="function",
        params=gen_binary_index()
    )
    def get_hamming_index(self, request, connect):
        logging.getLogger().info(request.param)
        if request.param["index_type"] in binary_support():
            return request.param
        # else:
        #     pytest.skip("Skip index Temporary")

    @pytest.fixture(
        scope="function",
        params=gen_binary_index()
    )
    def get_structure_index(self, request, connect):
        logging.getLogger().info(request.param)
        if request.param["index_type"] == "FLAT":
            return request.param
        # else:
        #     pytest.skip("Skip index Temporary")

    """
    generate top-k params
    """

    @pytest.fixture(
        scope="function",
        params=[1, 10]
    )
    def get_top_k(self, request):
        yield request.param

    @pytest.fixture(
        scope="function",
        params=[1, 10, 1100]
    )
    def get_nq(self, request):
        yield request.param

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_search_flat(self, connect, collection, get_top_k, get_nq):
        '''
        target: test basic search function, all the search params is correct, change top-k value
        method: search with the given vectors, check the result
        expected: the length of the result is top_k
        '''
        top_k = get_top_k
        nq = get_nq
        entities, ids = init_data(connect, collection)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq)
        if top_k <= max_top_k:
            connect.load_collection(collection)
            res = connect.search(collection, query)
            assert len(res[0]) == top_k
            assert res[0]._distances[0] <= epsilon
            assert check_id_result(res[0], ids[0])
        else:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_flat_top_k(self, connect, collection, get_nq):
        '''
        target: test basic search function, all the search params is correct, change top-k value
        method: search with the given vectors, check the result
        expected: the length of the result is top_k
        '''
        top_k = 16385
        nq = get_nq
        entities, ids = init_data(connect, collection)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq)
        if top_k <= max_top_k:
            connect.load_collection(collection)
            res = connect.search(collection, query)
            assert len(res[0]) == top_k
            assert res[0]._distances[0] <= epsilon
            assert check_id_result(res[0], ids[0])
        else:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query)

    @pytest.mark.skip("r0.3-test")
    def _test_search_field(self, connect, collection, get_top_k, get_nq):
        '''
        target: test basic search function, all the search params is correct, change top-k value
        method: search with the given vectors, check the result
        expected: the length of the result is top_k
        '''
        top_k = get_top_k
        nq = get_nq
        entities, ids = init_data(connect, collection)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq)
        if top_k <= max_top_k:
            connect.load_collection(collection)
            res = connect.search(collection, query, fields=["float_vector"])
            assert len(res[0]) == top_k
            assert res[0]._distances[0] <= epsilon
            assert check_id_result(res[0], ids[0])
            res = connect.search(collection, query, fields=["float"])
            for i in range(nq):
                assert entities[1]["values"][:nq][i] in [r.entity.get('float') for r in res[i]]
        else:
            with pytest.raises(Exception):
                connect.search(collection, query)

    def _test_search_after_delete(self, connect, collection, get_top_k, get_nq):
        '''
        target: test basic search function before and after deletion, all the search params is
                correct, change top-k value.
                check issue <a href="https://github.com/milvus-io/milvus/issues/4200">#4200</a>
        method: search with the given vectors, check the result
        expected: the deleted entities do not exist in the result.
        '''
        top_k = get_top_k
        nq = get_nq

        entities, ids = init_data(connect, collection, nb=10000)
        first_int64_value = entities[0]["values"][0]
        first_vector = entities[2]["values"][0]

        search_param = get_search_param("FLAT")
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq, search_params=search_param)
        vecs[:] = []
        vecs.append(first_vector)

        res = None
        if top_k > max_top_k:
            with pytest.raises(Exception):
                connect.search(collection, query, fields=['int64'])
            # pytest.skip("top_k value is larger than max_topp_k")
            pass
        else:
            res = connect.search(collection, query, fields=['int64'])
            assert len(res) == 1
            assert len(res[0]) >= top_k
            assert res[0][0].id == ids[0]
            assert res[0][0].entity.get("int64") == first_int64_value
            assert res[0]._distances[0] < epsilon
            assert check_id_result(res[0], ids[0])

        connect.delete_entity_by_id(collection, ids[:1])
        connect.flush([collection])

        res2 = connect.search(collection, query, fields=['int64'])
        assert len(res2) == 1
        assert len(res2[0]) >= top_k
        assert res2[0][0].id != ids[0]
        if top_k > 1:
            assert res2[0][0].id == res[0][1].id
            assert res2[0][0].entity.get("int64") == res[0][1].entity.get("int64")

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_after_index(self, connect, collection, get_simple_index, get_top_k, get_nq):
        '''
        target: test basic search function, all the search params is correct, test all index params, and build
        method: search with the given vectors, check the result
        expected: the length of the result is top_k
        '''
        top_k = get_top_k
        nq = get_nq

        index_type = get_simple_index["index_type"]
        if index_type in skip_pq():
            pytest.skip("Skip PQ")
        entities, ids = init_data(connect, collection)
        connect.create_index(collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq, search_params=search_param)
        if top_k > max_top_k:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query)
        else:
            connect.load_collection(collection)
            res = connect.search(collection, query)
            assert len(res) == nq
            assert len(res[0]) >= top_k
            assert res[0]._distances[0] < epsilon
            assert check_id_result(res[0], ids[0])

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_after_index_different_metric_type(self, connect, collection, get_simple_index):
        '''
        target: test search with different metric_type
        method: build index with L2, and search using IP
        expected: search ok
        '''
        search_metric_type = "IP"
        index_type = get_simple_index["index_type"]
        entities, ids = init_data(connect, collection)
        connect.create_index(collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, default_top_k, nq, metric_type=search_metric_type,
                                        search_params=search_param)
        connect.load_collection(collection)
        if index_type == "FLAT": 
            res = connect.search(collection, query)
            assert len(res) == nq
            assert len(res[0]) == default_top_k
            assert res[0]._distances[0] > res[0]._distances[default_top_k - 1]
        else:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_index_empty_partition(self, connect, collection, get_simple_index, get_top_k, get_nq):
        '''
        target: test basic search function, all the search params is correct, test all index params, and build
        method: add vectors into collection, search with the given vectors, check the result
        expected: the length of the result is top_k, search collection with partition tag return empty
        '''
        top_k = get_top_k
        nq = get_nq

        index_type = get_simple_index["index_type"]
        if index_type in skip_pq():
            pytest.skip("Skip PQ")
        connect.create_partition(collection, default_tag)
        entities, ids = init_data(connect, collection)
        connect.create_index(collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq, search_params=search_param)
        if top_k > max_top_k:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query)
        else:
            connect.load_collection(collection)
            res = connect.search(collection, query)
            assert len(res) == nq
            assert len(res[0]) >= top_k
            assert res[0]._distances[0] < epsilon
            assert check_id_result(res[0], ids[0])
            connect.release_collection(collection)
            connect.load_partitions(collection, [default_tag])
            res = connect.search(collection, query, partition_names=[default_tag])
            assert len(res[0]) == 0

    @pytest.mark.tags(CaseLabel.L2)
    @pytest.mark.timeout(600)
    def test_search_index_partition(self, connect, collection, get_simple_index, get_top_k, get_nq):
        '''
        target: test basic search function, all the search params is correct, test all index params, and build
        method: search with the given vectors, check the result
        expected: the length of the result is top_k
        '''
        top_k = get_top_k
        nq = get_nq

        index_type = get_simple_index["index_type"]
        if index_type in skip_pq():
            pytest.skip("Skip PQ")
        connect.create_partition(collection, default_tag)
        entities, ids = init_data(connect, collection, partition_names=default_tag)
        connect.create_index(collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq, search_params=search_param)
        if top_k > max_top_k:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query, partition_names=[default_tag])
        else:
            connect.load_partitions(collection, [default_tag])
            res = connect.search(collection, query, partition_names=[default_tag])
            assert len(res) == nq
            assert len(res[0]) == top_k
            assert res[0]._distances[0] < epsilon
            assert check_id_result(res[0], ids[0])


    @pytest.mark.tags(CaseLabel.L2)
    def test_search_index_partition_not_existed(self, connect, collection, get_top_k, get_nq, get_simple_index):
        '''
        target: test basic search function, all the search params is correct, test all index params, and build
        method: search with the given vectors and tag (tag name not existed in collection), check the result
        expected: error raised
        '''
        top_k = get_top_k
        nq = get_nq
        entities, ids = init_data(connect, collection)
        connect.create_index(collection, field_name, get_simple_index)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq)
        if top_k > max_top_k:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query, partition_names=["new_tag"])
        else:
            connect.load_collection(collection)
            with pytest.raises(Exception) as e:
                connect.search(collection, query, partition_names=["new_tag"])

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_index_partitions(self, connect, collection, get_simple_index, get_top_k):
        '''
        target: test basic search function, all the search params is correct, test all index params, and build
        method: search collection with the given vectors and tags, check the result
        expected: the length of the result is top_k
        '''
        top_k = get_top_k
        nq = 2
        new_tag = "new_tag"
        index_type = get_simple_index["index_type"]
        if index_type in skip_pq():
            pytest.skip("Skip PQ")
        connect.create_partition(collection, default_tag)
        connect.create_partition(collection, new_tag)
        entities, ids = init_data(connect, collection, partition_names=default_tag)
        new_entities, new_ids = init_data(connect, collection, nb=6001, partition_names=new_tag)
        connect.create_index(collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq, search_params=search_param)
        if top_k > max_top_k:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query)
        else:
            connect.load_collection(collection)
            res = connect.search(collection, query)
            assert check_id_result(res[0], ids[0])
            assert not check_id_result(res[1], new_ids[0])
            assert res[0]._distances[0] < epsilon
            assert res[1]._distances[0] < epsilon
            res = connect.search(collection, query, partition_names=[new_tag])
            assert res[0]._distances[0] > epsilon
            assert res[1]._distances[0] > epsilon
            connect.release_collection(collection)

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_index_partitions_B(self, connect, collection, get_simple_index, get_top_k):
        '''
        target: test basic search function, all the search params is correct, test all index params, and build
        method: search collection with the given vectors and tags, check the result
        expected: the length of the result is top_k
        '''
        top_k = get_top_k
        nq = 2
        tag = "tag"
        new_tag = "new_tag"
        index_type = get_simple_index["index_type"]
        if index_type in skip_pq():
            pytest.skip("Skip PQ")
        connect.create_partition(collection, tag)
        connect.create_partition(collection, new_tag)
        entities, ids = init_data(connect, collection, partition_names=tag)
        new_entities, new_ids = init_data(connect, collection, nb=6001, partition_names=new_tag)
        connect.create_index(collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        print(f'entities[-1]["values"][:1]: {entities[-1]["values"][:1]}')
        print(f'new_entities[-1]["values"][:1]: {new_entities[-1]["values"][:1]}')
        query, vecs = gen_query_vectors(field_name, new_entities, top_k, nq, search_params=search_param,
                                        replace_vecs=[entities[-1]["values"][:1][0], new_entities[-1]["values"][:1][0]])
        if top_k > max_top_k:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query)
        else:
            connect.load_collection(collection)
            res = connect.search(collection, query, partition_names=["(.*)tag"])
            assert check_id_result(res[0], ids[0])
            assert check_id_result(res[0], new_ids[0])
            assert res[0]._distances[0] < epsilon
            assert res[1]._distances[0] < epsilon
            res = connect.search(collection, query, partition_names=["new(.*)"])
            assert not check_id_result(res[0], ids[0])
            assert check_id_result(res[1], new_ids[0])
            assert res[0]._distances[0] > epsilon
            assert res[1]._distances[0] < epsilon
            connect.release_collection(collection)

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_ip_flat(self, connect, collection, get_simple_index, get_top_k, get_nq):
        '''
        target: test basic search function, all the search params is correct, change top-k value
        method: search with the given vectors, check the result
        expected: the length of the result is top_k
        '''
        top_k = get_top_k
        nq = get_nq
        entities, ids = init_data(connect, collection)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq, metric_type="IP")
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res[0]) == top_k
        assert res[0]._distances[0] >= 1 - gen_inaccuracy(res[0]._distances[0])
        assert check_id_result(res[0], ids[0])

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_ip_after_index(self, connect, collection, get_simple_index, get_top_k, get_nq):
        '''
        target: test basic search function, all the search params is correct, test all index params, and build
        method: search with the given vectors, check the result
        expected: the length of the result is top_k
        '''
        top_k = get_top_k
        nq = get_nq

        index_type = get_simple_index["index_type"]
        if index_type in skip_pq():
            pytest.skip("Skip PQ")
        entities, ids = init_data(connect, collection)
        get_simple_index["metric_type"] = "IP"
        connect.create_index(collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq, metric_type="IP", search_params=search_param)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) >= top_k
        assert check_id_result(res[0], ids[0])
        assert res[0]._distances[0] >= 1 - gen_inaccuracy(res[0]._distances[0])

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_ip_index_empty_partition(self, connect, collection, get_simple_index, get_top_k, get_nq):
        '''
        target: test basic search function, all the search params is correct, test all index params, and build
        method: add vectors into collection, search with the given vectors, check the result
        expected: the length of the result is top_k, search collection with partition tag return empty
        '''
        top_k = get_top_k
        nq = get_nq
        metric_type = "IP"
        index_type = get_simple_index["index_type"]
        if index_type in skip_pq():
            pytest.skip("Skip PQ")
        connect.create_partition(collection, default_tag)
        entities, ids = init_data(connect, collection)
        get_simple_index["metric_type"] = metric_type
        connect.create_index(collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq, metric_type=metric_type,
                                        search_params=search_param)
        if top_k > max_top_k:
            with pytest.raises(Exception) as e:
                res = connect.search(collection, query)
        else:
            connect.load_collection(collection)
            res = connect.search(collection, query)
            assert len(res) == nq
            assert len(res[0]) >= top_k
            assert res[0]._distances[0] >= 1 - gen_inaccuracy(res[0]._distances[0])
            assert check_id_result(res[0], ids[0])
            res = connect.search(collection, query, partition_names=[default_tag])
            assert len(res[0]) == 0

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_ip_index_partitions(self, connect, collection, get_simple_index, get_top_k):
        '''
        target: test basic search function, all the search params is correct, test all index params, and build
        method: search collection with the given vectors and tags, check the result
        expected: the length of the result is top_k
        '''
        top_k = get_top_k
        nq = 2
        metric_type = "IP"
        new_tag = "new_tag"
        index_type = get_simple_index["index_type"]
        if index_type in skip_pq():
            pytest.skip("Skip PQ")
        connect.create_partition(collection, default_tag)
        connect.create_partition(collection, new_tag)
        entities, ids = init_data(connect, collection, partition_names=default_tag)
        new_entities, new_ids = init_data(connect, collection, nb=6001, partition_names=new_tag)
        get_simple_index["metric_type"] = metric_type
        connect.create_index(collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, top_k, nq, metric_type="IP", search_params=search_param)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert check_id_result(res[0], ids[0])
        assert not check_id_result(res[1], new_ids[0])
        assert res[0]._distances[0] >= 1 - gen_inaccuracy(res[0]._distances[0])
        assert res[1]._distances[0] >= 1 - gen_inaccuracy(res[1]._distances[0])
        res = connect.search(collection, query, partition_names=["new_tag"])
        assert res[0]._distances[0] < 1 - gen_inaccuracy(res[0]._distances[0])
        # TODO:
        # assert res[1]._distances[0] >= 1 - gen_inaccuracy(res[1]._distances[0])

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_without_connect(self, dis_connect, collection):
        '''
        target: test search vectors without connection
        method: use dis connected instance, call search method and check if search successfully
        expected: raise exception
        '''
        with pytest.raises(Exception) as e:
            res = dis_connect.search(collection, default_query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_collection_not_existed(self, connect):
        '''
        target: search collection not existed
        method: search with the random collection_name, which is not in db
        expected: status not ok
        '''
        collection_name = gen_unique_str(uid)
        with pytest.raises(Exception) as e:
            res = connect.search(collection_name, default_query)

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_search_distance_l2(self, connect, collection):
        '''
        target: search collection, and check the result: distance
        method: compare the return distance value with value computed with Euclidean
        expected: the return distance equals to the computed value
        '''
        nq = 2
        search_param = {"nprobe": 1}
        entities, ids = init_data(connect, collection, nb=nq)
        query, vecs = gen_query_vectors(field_name, entities, default_top_k, nq, rand_vector=True,
                                        search_params=search_param)
        inside_query, inside_vecs = gen_query_vectors(field_name, entities, default_top_k, nq,
                                                      search_params=search_param)
        distance_0 = l2(vecs[0], inside_vecs[0])
        distance_1 = l2(vecs[0], inside_vecs[1])
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert abs(np.sqrt(res[0]._distances[0]) - min(distance_0, distance_1)) <= gen_inaccuracy(res[0]._distances[0])

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_distance_l2_after_index(self, connect, id_collection, get_simple_index):
        '''
        target: search collection, and check the result: distance
        method: compare the return distance value with value computed with Inner product
        expected: the return distance equals to the computed value
        '''
        index_type = get_simple_index["index_type"]
        nq = 2
        entities, ids = init_data(connect, id_collection, auto_id=False)
        connect.create_index(id_collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, default_top_k, nq, rand_vector=True,
                                        search_params=search_param)
        inside_vecs = entities[-1]["values"]
        min_distance = 1.0
        min_id = None
        for i in range(default_nb):
            tmp_dis = l2(vecs[0], inside_vecs[i])
            if min_distance > tmp_dis:
                min_distance = tmp_dis
                min_id = ids[i]
        connect.load_collection(id_collection)
        res = connect.search(id_collection, query)
        tmp_epsilon = epsilon
        check_id_result(res[0], min_id)
        # if index_type in ["ANNOY", "IVF_PQ"]:
        #     tmp_epsilon = 0.1
        # TODO:
        # assert abs(np.sqrt(res[0]._distances[0]) - min_distance) <= tmp_epsilon

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_distance_ip(self, connect, collection):
        '''
        target: search collection, and check the result: distance
        method: compare the return distance value with value computed with Inner product
        expected: the return distance equals to the computed value
        '''
        nq = 2
        metirc_type = "IP"
        search_param = {"nprobe": 1}
        entities, ids = init_data(connect, collection, nb=nq)
        query, vecs = gen_query_vectors(field_name, entities, default_top_k, nq, rand_vector=True,
                                        metric_type=metirc_type,
                                        search_params=search_param)
        inside_query, inside_vecs = gen_query_vectors(field_name, entities, default_top_k, nq,
                                                      search_params=search_param)
        distance_0 = ip(vecs[0], inside_vecs[0])
        distance_1 = ip(vecs[0], inside_vecs[1])
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert abs(res[0]._distances[0] - max(distance_0, distance_1)) <= epsilon

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_distance_ip_after_index(self, connect, id_collection, get_simple_index):
        '''
        target: search collection, and check the result: distance
        method: compare the return distance value with value computed with Inner product
        expected: the return distance equals to the computed value
        '''
        index_type = get_simple_index["index_type"]
        nq = 2
        metirc_type = "IP"
        entities, ids = init_data(connect, id_collection, auto_id=False)
        get_simple_index["metric_type"] = metirc_type
        connect.create_index(id_collection, field_name, get_simple_index)
        search_param = get_search_param(index_type)
        query, vecs = gen_query_vectors(field_name, entities, default_top_k, nq, rand_vector=True,
                                        metric_type=metirc_type,
                                        search_params=search_param)
        inside_vecs = entities[-1]["values"]
        max_distance = 0
        max_id = None
        for i in range(default_nb):
            tmp_dis = ip(vecs[0], inside_vecs[i])
            if max_distance < tmp_dis:
                max_distance = tmp_dis
                max_id = ids[i]
        connect.load_collection(id_collection)
        res = connect.search(id_collection, query)
        tmp_epsilon = epsilon
        check_id_result(res[0], max_id)
        # if index_type in ["ANNOY", "IVF_PQ"]:
        #     tmp_epsilon = 0.1
        # TODO:
        # assert abs(res[0]._distances[0] - max_distance) <= tmp_epsilon

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_search_distance_jaccard_flat_index(self, connect, binary_collection):
        '''
        target: search binary_collection, and check the result: distance
        method: compare the return distance value with value computed with L2
        expected: the return distance equals to the computed value
        '''
        nq = 1
        int_vectors, entities, ids = init_binary_data(connect, binary_collection, nb=2)
        query_int_vectors, query_entities, tmp_ids = init_binary_data(connect, binary_collection, nb=1, insert=False)
        distance_0 = jaccard(query_int_vectors[0], int_vectors[0])
        distance_1 = jaccard(query_int_vectors[0], int_vectors[1])
        query, vecs = gen_query_vectors(binary_field_name, query_entities, default_top_k, nq, metric_type="JACCARD")
        connect.load_collection(binary_collection)
        res = connect.search(binary_collection, query)
        assert abs(res[0]._distances[0] - min(distance_0, distance_1)) <= epsilon

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_binary_flat_with_L2(self, connect, binary_collection):
        '''
        target: search binary_collection, and check the result: distance
        method: compare the return distance value with value computed with L2
        expected: the return distance equals to the computed value
        '''
        nq = 1
        int_vectors, entities, ids = init_binary_data(connect, binary_collection, nb=2)
        query_int_vectors, query_entities, tmp_ids = init_binary_data(connect, binary_collection, nb=1, insert=False)
        query, vecs = gen_query_vectors(binary_field_name, query_entities, default_top_k, nq, metric_type="L2")
        with pytest.raises(Exception) as e:
            connect.search(binary_collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_distance_hamming_flat_index(self, connect, binary_collection):
        '''
        target: search binary_collection, and check the result: distance
        method: compare the return distance value with value computed with Inner product
        expected: the return distance equals to the computed value
        '''
        nq = 1
        int_vectors, entities, ids = init_binary_data(connect, binary_collection, nb=2)
        query_int_vectors, query_entities, tmp_ids = init_binary_data(connect, binary_collection, nb=1, insert=False)
        distance_0 = hamming(query_int_vectors[0], int_vectors[0])
        distance_1 = hamming(query_int_vectors[0], int_vectors[1])
        query, vecs = gen_query_vectors(binary_field_name, query_entities, default_top_k, nq, metric_type="HAMMING")
        connect.load_collection(binary_collection)
        res = connect.search(binary_collection, query)
        assert abs(res[0][0].distance - min(distance_0, distance_1).astype(float)) <= epsilon

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_distance_substructure_flat_index(self, connect, binary_collection):
        '''
        target: search binary_collection, and check the result: distance
        method: search with new random binary entities and SUBSTRUCTURE metric type
        expected: the return distance equals to the computed value
        '''
        nq = 1
        int_vectors, entities, ids = init_binary_data(connect, binary_collection, nb=2)
        query_int_vectors, query_entities, tmp_ids = init_binary_data(connect, binary_collection, nb=1, insert=False)
        distance_0 = substructure(query_int_vectors[0], int_vectors[0])
        distance_1 = substructure(query_int_vectors[0], int_vectors[1])
        query, vecs = gen_query_vectors(binary_field_name, query_entities, default_top_k, nq,
                                        metric_type="SUBSTRUCTURE")
        connect.load_collection(binary_collection)
        res = connect.search(binary_collection, query)
        assert len(res[0]) == 0

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_distance_substructure_flat_index_B(self, connect, binary_collection):
        '''
        target: search binary_collection, and check the result: distance
        method: search with entities that related to inserted entities
        expected: the return distance equals to the computed value
        '''
        top_k = 3
        int_vectors, entities, ids = init_binary_data(connect, binary_collection, nb=2)
        query_int_vectors, query_vecs = gen_binary_sub_vectors(int_vectors, 2)
        query, vecs = gen_query_vectors(binary_field_name, entities, top_k, nq, metric_type="SUBSTRUCTURE",
                                        replace_vecs=query_vecs)
        connect.load_collection(binary_collection)
        res = connect.search(binary_collection, query)
        assert res[0][0].distance <= epsilon
        assert res[0][0].id == ids[0]
        assert res[1][0].distance <= epsilon
        assert res[1][0].id == ids[1]

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_distance_superstructure_flat_index(self, connect, binary_collection):
        '''
        target: search binary_collection, and check the result: distance
        method: compare the return distance value with value computed with Inner product
        expected: the return distance equals to the computed value
        '''
        nq = 1
        int_vectors, entities, ids = init_binary_data(connect, binary_collection, nb=2)
        query_int_vectors, query_entities, tmp_ids = init_binary_data(connect, binary_collection, nb=1, insert=False)
        distance_0 = superstructure(query_int_vectors[0], int_vectors[0])
        distance_1 = superstructure(query_int_vectors[0], int_vectors[1])
        query, vecs = gen_query_vectors(binary_field_name, query_entities, default_top_k, nq,
                                        metric_type="SUPERSTRUCTURE")
        connect.load_collection(binary_collection)
        res = connect.search(binary_collection, query)
        assert len(res[0]) == 0

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_distance_superstructure_flat_index_B(self, connect, binary_collection):
        '''
        target: search binary_collection, and check the result: distance
        method: compare the return distance value with value computed with SUPER
        expected: the return distance equals to the computed value
        '''
        top_k = 3
        int_vectors, entities, ids = init_binary_data(connect, binary_collection, nb=2)
        query_int_vectors, query_vecs = gen_binary_super_vectors(int_vectors, 2)
        query, vecs = gen_query_vectors(binary_field_name, entities, top_k, nq, metric_type="SUPERSTRUCTURE",
                                        replace_vecs=query_vecs)
        connect.load_collection(binary_collection)
        res = connect.search(binary_collection, query)
        assert len(res[0]) == 2
        assert len(res[1]) == 2
        assert res[0][0].id in ids
        assert res[0][0].distance <= epsilon
        assert res[1][0].id in ids
        assert res[1][0].distance <= epsilon

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_distance_tanimoto_flat_index(self, connect, binary_collection):
        '''
        target: search binary_collection, and check the result: distance
        method: compare the return distance value with value computed with Inner product
        expected: the return distance equals to the computed value
        '''
        nq = 1
        int_vectors, entities, ids = init_binary_data(connect, binary_collection, nb=2)
        query_int_vectors, query_entities, tmp_ids = init_binary_data(connect, binary_collection, nb=1, insert=False)
        distance_0 = tanimoto(query_int_vectors[0], int_vectors[0])
        distance_1 = tanimoto(query_int_vectors[0], int_vectors[1])
        query, vecs = gen_query_vectors(binary_field_name, query_entities, default_top_k, nq, metric_type="TANIMOTO")
        connect.load_collection(binary_collection)
        res = connect.search(binary_collection, query)
        assert abs(res[0][0].distance - min(distance_0, distance_1)) <= epsilon

    @pytest.mark.tags(CaseLabel.L2)
    @pytest.mark.timeout(300)
    def test_search_concurrent_multithreads(self, connect, args):
        '''
        target: test concurrent search with multiprocessess
        method: search with 10 processes, each process uses dependent connection
        expected: status ok and the returned vectors should be query_records
        '''
        nb = 100
        top_k = 10
        threads_num = 4
        threads = []
        collection = gen_unique_str(uid)
        uri = "tcp://%s:%s" % (args["ip"], args["port"])
        # create collection
        milvus = get_milvus(args["ip"], args["port"], handler=args["handler"])
        milvus.create_collection(collection, default_fields)
        entities, ids = init_data(milvus, collection)
        connect.load_collection(collection)

        def search(milvus):
            res = milvus.search(collection, default_query)
            assert len(res) == 1
            assert res[0]._entities[0].id in ids
            assert res[0]._distances[0] < epsilon

        for i in range(threads_num):
            milvus = get_milvus(args["ip"], args["port"], handler=args["handler"])
            t = MyThread(target=search, args=(milvus,))
            threads.append(t)
            t.start()
            time.sleep(0.2)
        for t in threads:
            t.join()

    @pytest.mark.tags(CaseLabel.L2)
    @pytest.mark.timeout(300)
    def test_search_concurrent_multithreads_single_connection(self, connect, args):
        '''
        target: test concurrent search with multiprocessess
        method: search with 10 processes, each process uses dependent connection
        expected: status ok and the returned vectors should be query_records
        '''
        nb = 100
        top_k = 10
        threads_num = 4
        threads = []
        collection = gen_unique_str(uid)
        uri = "tcp://%s:%s" % (args["ip"], args["port"])
        # create collection
        milvus = get_milvus(args["ip"], args["port"], handler=args["handler"])
        milvus.create_collection(collection, default_fields)
        entities, ids = init_data(milvus, collection)
        connect.load_collection(collection)

        def search(milvus):
            res = milvus.search(collection, default_query)
            assert len(res) == 1
            assert res[0]._entities[0].id in ids
            assert res[0]._distances[0] < epsilon

        for i in range(threads_num):
            t = MyThread(target=search, args=(milvus,))
            threads.append(t)
            t.start()
            time.sleep(0.2)
        for t in threads:
            t.join()

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_multi_collections(self, connect, args):
        '''
        target: test search multi collections of L2
        method: add vectors into 10 collections, and search
        expected: search status ok, the length of result
        '''
        num = 10
        top_k = 10
        nq = 20
        collection_names = []
        for i in range(num):
            collection = gen_unique_str(uid + str(i))
            connect.create_collection(collection, default_fields)
            collection_names.append(collection)
            entities, ids = init_data(connect, collection)
            assert len(ids) == default_nb
            query, vecs = gen_query_vectors(field_name, entities, top_k, nq, search_params=search_param)
            connect.load_collection(collection)
            res = connect.search(collection, query)
            assert len(res) == nq
            for i in range(nq):
                assert check_id_result(res[i], ids[i])
                assert res[i]._distances[0] < epsilon
                assert res[i]._distances[1] > epsilon
        for i in range(num):
            connect.drop_collection(collection_names[i])

    @pytest.mark.skip("r0.3-test")
    def _test_query_entities_with_field_less_than_top_k(self, connect, id_collection):
        """
        target: test search with field, and let return entities less than topk
        method: insert entities and build ivf_ index, and search with field, n_probe=1
        expected:
        """
        entities, ids = init_data(connect, id_collection, auto_id=False)
        simple_index = {"index_type": "IVF_FLAT", "params": {"nlist": 200}, "metric_type": "L2"}
        connect.create_index(id_collection, field_name, simple_index)
        # logging.getLogger().info(connect.get_collection_info(id_collection))
        top_k = 300
        default_query, default_query_vecs = gen_query_vectors(field_name, entities, top_k, nq,
                                                              search_params={"nprobe": 1})
        expr = {"must": [gen_default_vector_expr(default_query)]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(id_collection)
        res = connect.search(id_collection, query, fields=["int64"])
        assert len(res) == nq
        for r in res[0]:
            assert getattr(r.entity, "int64") == getattr(r.entity, "id")


class TestSearchDSL(object):
    """
    ******************************************************************
    #  The following cases are used to build invalid query expr
    ******************************************************************
    """
    @pytest.mark.tags(CaseLabel.L2)
    def test_query_no_must(self, connect, collection):
        '''
        method: build query without must expr
        expected: error raised
        '''
        # entities, ids = init_data(connect, collection)
        query = update_query_expr(default_query, keep_old=False)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_no_vector_term_only(self, connect, collection):
        '''
        method: build query without vector only term
        expected: error raised
        '''
        # entities, ids = init_data(connect, collection)
        expr = {
            "must": [gen_default_term_expr]
        }
        query = update_query_expr(default_query, keep_old=False, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_no_vector_range_only(self, connect, collection):
        '''
        method: build query without vector only range
        expected: error raised
        '''
        # entities, ids = init_data(connect, collection)
        expr = {
            "must": [gen_default_range_expr]
        }
        query = update_query_expr(default_query, keep_old=False, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_vector_only(self, connect, collection):
        entities, ids = init_data(connect, collection)
        connect.load_collection(collection)
        res = connect.search(collection, default_query)
        assert len(res) == nq
        assert len(res[0]) == default_top_k

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_wrong_format(self, connect, collection):
        '''
        method: build query without must expr, with wrong expr name
        expected: error raised
        '''
        # entities, ids = init_data(connect, collection)
        expr = {
            "must1": [gen_default_term_expr]
        }
        query = update_query_expr(default_query, keep_old=False, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_empty(self, connect, collection):
        '''
        method: search with empty query
        expected: error raised
        '''
        query = {}
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    """
    ******************************************************************
    #  The following cases are used to build valid query expr
    ******************************************************************
    """
    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_value_not_in(self, connect, collection):
        '''
        method: build query with vector and term expr, with no term can be filtered
        expected: filter pass
        '''
        entities, ids = init_data(connect, collection)
        expr = {
            "must": [gen_default_vector_expr(default_query), gen_default_term_expr(values=[100000])]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 0
        # TODO:

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_value_all_in(self, connect, collection):
        '''
        method: build query with vector and term expr, with all term can be filtered
        expected: filter pass
        '''
        entities, ids = init_data(connect, collection)
        expr = {"must": [gen_default_vector_expr(default_query), gen_default_term_expr(values=[1])]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 1
        # TODO:

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_values_not_in(self, connect, collection):
        '''
        method: build query with vector and term expr, with no term can be filtered
        expected: filter pass
        '''
        entities, ids = init_data(connect, collection)
        expr = {"must": [gen_default_vector_expr(default_query),
                         gen_default_term_expr(values=[i for i in range(100000, 100010)])]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 0
        # TODO:

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_values_all_in(self, connect, collection):
        '''
        method: build query with vector and term expr, with all term can be filtered
        expected: filter pass
        '''
        entities, ids = init_data(connect, collection)
        expr = {"must": [gen_default_vector_expr(default_query), gen_default_term_expr()]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == default_top_k
        limit = default_nb // 2
        for i in range(nq):
            for result in res[i]:
                logging.getLogger().info(result.id)
                assert result.id in ids[:limit]
        # TODO:

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_values_parts_in(self, connect, collection):
        '''
        method: build query with vector and term expr, with parts of term can be filtered
        expected: filter pass
        '''
        entities, ids = init_data(connect, collection)
        expr = {"must": [gen_default_vector_expr(default_query),
                         gen_default_term_expr(
                             values=[i for i in range(default_nb // 2, default_nb + default_nb // 2)])]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == default_top_k
        # TODO:

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_values_repeat(self, connect, collection):
        '''
        method: build query with vector and term expr, with the same values
        expected: filter pass
        '''
        entities, ids = init_data(connect, collection)
        expr = {
            "must": [gen_default_vector_expr(default_query),
                     gen_default_term_expr(values=[1 for i in range(1, default_nb)])]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 1
        # TODO:

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_value_empty(self, connect, collection):
        '''
        method: build query with term value empty
        expected: return null
        '''
        expr = {"must": [gen_default_vector_expr(default_query), gen_default_term_expr(values=[])]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 0

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_complex_dsl(self, connect, collection):
        '''
        method: query with complicated dsl
        expected: no error raised
        '''
        expr = {"must": [
            {"must": [{"should": [gen_default_term_expr(values=[1]), gen_default_range_expr()]}]},
            {"must": [gen_default_vector_expr(default_query)]}
        ]}
        logging.getLogger().info(expr)
        query = update_query_expr(default_query, expr=expr)
        logging.getLogger().info(query)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        logging.getLogger().info(res)

    """
    ******************************************************************
    #  The following cases are used to build invalid term query expr
    ******************************************************************
    """

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_key_error(self, connect, collection):
        '''
        method: build query with term key error
        expected: Exception raised
        '''
        expr = {"must": [gen_default_vector_expr(default_query),
                         gen_default_term_expr(keyword="terrm", values=[i for i in range(default_nb // 2)])]}
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.fixture(
        scope="function",
        params=gen_invalid_term()
    )
    def get_invalid_term(self, request):
        return request.param

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_wrong_format(self, connect, collection, get_invalid_term):
        '''
        method: build query with wrong format term
        expected: Exception raised
        '''
        entities, ids = init_data(connect, collection)
        term = get_invalid_term
        expr = {"must": [gen_default_vector_expr(default_query), term]}
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_field_named_term(self, connect, collection):
        '''
        method: build query with field named "term"
        expected: error raised
        '''
        term_fields = add_field_default(default_fields, field_name="term")
        collection_term = gen_unique_str("term")
        connect.create_collection(collection_term, term_fields)
        term_entities = add_field(entities, field_name="term")
        ids = connect.insert(collection_term, term_entities)
        assert len(ids) == default_nb
        connect.flush([collection_term])
        # count = connect.count_entities(collection_term)
        # assert count == default_nb
        stats = connect.get_collection_stats(collection_term)
        assert stats["row_count"] == default_nb
        term_param = {"term": {"term": {"values": [i for i in range(default_nb // 2)]}}}
        expr = {"must": [gen_default_vector_expr(default_query),
                         term_param]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection_term)
        res = connect.search(collection_term, query)
        assert len(res) == nq
        assert len(res[0]) == default_top_k
        connect.drop_collection(collection_term)

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_term_one_field_not_existed(self, connect, collection):
        '''
        method: build query with two fields term, one of it not existed
        expected: exception raised
        '''
        entities, ids = init_data(connect, collection)
        term = gen_default_term_expr()
        term["term"].update({"a": [0]})
        expr = {"must": [gen_default_vector_expr(default_query), term]}
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    """
    ******************************************************************
    #  The following cases are used to build valid range query expr
    ******************************************************************
    """

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_range_key_error(self, connect, collection):
        '''
        method: build query with range key error
        expected: Exception raised
        '''
        range = gen_default_range_expr(keyword="ranges")
        expr = {"must": [gen_default_vector_expr(default_query), range]}
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.fixture(
        scope="function",
        params=gen_invalid_range()
    )
    def get_invalid_range(self, request):
        return request.param

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_range_wrong_format(self, connect, collection, get_invalid_range):
        '''
        method: build query with wrong format range
        expected: Exception raised
        '''
        entities, ids = init_data(connect, collection)
        range = get_invalid_range
        expr = {"must": [gen_default_vector_expr(default_query), range]}
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_range_string_ranges(self, connect, collection):
        '''
        method: build query with invalid ranges
        expected: raise Exception
        '''
        entities, ids = init_data(connect, collection)
        ranges = {"GT": "0", "LT": "1000"}
        range = gen_default_range_expr(ranges=ranges)
        expr = {"must": [gen_default_vector_expr(default_query), range]}
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_range_invalid_ranges(self, connect, collection):
        '''
        method: build query with invalid ranges
        expected: 0
        '''
        entities, ids = init_data(connect, collection)
        ranges = {"GT": default_nb, "LT": 0}
        range = gen_default_range_expr(ranges=ranges)
        expr = {"must": [gen_default_vector_expr(default_query), range]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res[0]) == 0

    @pytest.fixture(
        scope="function",
        params=gen_valid_ranges()
    )
    def get_valid_ranges(self, request):
        return request.param

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_range_valid_ranges(self, connect, collection, get_valid_ranges):
        '''
        method: build query with valid ranges
        expected: pass
        '''
        entities, ids = init_data(connect, collection)
        ranges = get_valid_ranges
        range = gen_default_range_expr(ranges=ranges)
        expr = {"must": [gen_default_vector_expr(default_query), range]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == default_top_k

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_range_one_field_not_existed(self, connect, collection):
        '''
        method: build query with two fields ranges, one of fields not existed
        expected: exception raised
        '''
        entities, ids = init_data(connect, collection)
        range = gen_default_range_expr()
        range["range"].update({"a": {"GT": 1, "LT": default_nb // 2}})
        expr = {"must": [gen_default_vector_expr(default_query), range]}
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    """
    ************************************************************************
    #  The following cases are used to build query expr multi range and term
    ************************************************************************
    """
    @pytest.mark.tags(CaseLabel.L2)
    def test_query_multi_term_has_common(self, connect, collection):
        '''
        method: build query with multi term with same field, and values has common
        expected: pass
        '''
        entities, ids = init_data(connect, collection)
        term_first = gen_default_term_expr()
        term_second = gen_default_term_expr(values=[i for i in range(default_nb // 3)])
        expr = {"must": [gen_default_vector_expr(default_query), term_first, term_second]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == default_top_k

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_multi_term_no_common(self, connect, collection):
        '''
         method: build query with multi range with same field, and ranges no common
         expected: pass
        '''
        entities, ids = init_data(connect, collection)
        term_first = gen_default_term_expr()
        term_second = gen_default_term_expr(values=[i for i in range(default_nb // 2, default_nb + default_nb // 2)])
        expr = {"must": [gen_default_vector_expr(default_query), term_first, term_second]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 0

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_multi_term_different_fields(self, connect, collection):
        '''
         method: build query with multi range with same field, and ranges no common
         expected: pass
        '''
        entities, ids = init_data(connect, collection)
        term_first = gen_default_term_expr()
        term_second = gen_default_term_expr(field="float",
                                            values=[float(i) for i in range(default_nb // 2, default_nb)])
        expr = {"must": [gen_default_vector_expr(default_query), term_first, term_second]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 0

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_single_term_multi_fields(self, connect, collection):
        '''
        method: build query with multi term, different field each term
        expected: pass
        '''
        entities, ids = init_data(connect, collection)
        term_first = {"int64": {"values": [i for i in range(default_nb // 2)]}}
        term_second = {"float": {"values": [float(i) for i in range(default_nb // 2, default_nb)]}}
        term = update_term_expr({"term": {}}, [term_first, term_second])
        expr = {"must": [gen_default_vector_expr(default_query), term]}
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_multi_range_has_common(self, connect, collection):
        '''
        method: build query with multi range with same field, and ranges has common
        expected: pass
        '''
        entities, ids = init_data(connect, collection)
        range_one = gen_default_range_expr()
        range_two = gen_default_range_expr(ranges={"GT": 1, "LT": default_nb // 3})
        expr = {"must": [gen_default_vector_expr(default_query), range_one, range_two]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == default_top_k

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_multi_range_no_common(self, connect, collection):
        '''
         method: build query with multi range with same field, and ranges no common
        expected: pass
        '''
        entities, ids = init_data(connect, collection)
        range_one = gen_default_range_expr()
        range_two = gen_default_range_expr(ranges={"GT": default_nb // 2, "LT": default_nb})
        expr = {"must": [gen_default_vector_expr(default_query), range_one, range_two]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 0

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_multi_range_different_fields(self, connect, collection):
        '''
        method: build query with multi range, different field each range
        expected: pass
        '''
        entities, ids = init_data(connect, collection)
        range_first = gen_default_range_expr()
        range_second = gen_default_range_expr(field="float", ranges={"GT": default_nb // 2, "LT": default_nb})
        expr = {"must": [gen_default_vector_expr(default_query), range_first, range_second]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 0

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_single_range_multi_fields(self, connect, collection):
        '''
        method: build query with multi range, different field each range
        expected: pass
        '''
        entities, ids = init_data(connect, collection)
        range_first = {"int64": {"GT": 0, "LT": default_nb // 2}}
        range_second = {"float": {"GT": default_nb / 2, "LT": float(default_nb)}}
        range = update_range_expr({"range": {}}, [range_first, range_second])
        expr = {"must": [gen_default_vector_expr(default_query), range]}
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    """
    ******************************************************************
    #  The following cases are used to build query expr both term and range
    ******************************************************************
    """
    @pytest.mark.tags(CaseLabel.L2)
    def test_query_single_term_range_has_common(self, connect, collection):
        '''
        method: build query with single term single range
        expected: pass
        '''
        entities, ids = init_data(connect, collection)
        term = gen_default_term_expr()
        range = gen_default_range_expr(ranges={"GT": -1, "LT": default_nb // 2})
        expr = {"must": [gen_default_vector_expr(default_query), term, range]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == default_top_k

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_single_term_range_no_common(self, connect, collection):
        '''
        method: build query with single term single range
        expected: pass
        '''
        entities, ids = init_data(connect, collection)
        term = gen_default_term_expr()
        range = gen_default_range_expr(ranges={"GT": default_nb // 2, "LT": default_nb})
        expr = {"must": [gen_default_vector_expr(default_query), term, range]}
        query = update_query_expr(default_query, expr=expr)
        connect.load_collection(collection)
        res = connect.search(collection, query)
        assert len(res) == nq
        assert len(res[0]) == 0

    """
    ******************************************************************
    #  The following cases are used to build multi vectors query expr
    ******************************************************************
    """
    @pytest.mark.tags(CaseLabel.L2)
    def test_query_multi_vectors_same_field(self, connect, collection):
        '''
        method: build query with two vectors same field
        expected: error raised
        '''
        entities, ids = init_data(connect, collection)
        vector1 = default_query
        vector2 = gen_query_vectors(field_name, entities, default_top_k, nq=2)
        expr = {
            "must": [vector1, vector2]
        }
        query = update_query_expr(default_query, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)


class TestSearchDSLBools(object):
    """
    ******************************************************************
    #  The following cases are used to build invalid query expr
    ******************************************************************
    """

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_no_bool(self, connect, collection):
        '''
        method: build query without bool expr
        expected: error raised
        '''
        entities, ids = init_data(connect, collection)
        expr = {"bool1": {}}
        query = expr
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_should_only_term(self, connect, collection):
        '''
        method: build query without must, with should.term instead
        expected: error raised
        '''
        expr = {"should": gen_default_term_expr}
        query = update_query_expr(default_query, keep_old=False, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_query_should_only_vector(self, connect, collection):
        '''
        method: build query without must, with should.vector instead
        expected: error raised
        '''
        expr = {"should": default_query["bool"]["must"]}
        query = update_query_expr(default_query, keep_old=False, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_must_not_only_term(self, connect, collection):
        '''
        method: build query without must, with must_not.term instead
        expected: error raised
        '''
        expr = {"must_not": gen_default_term_expr}
        query = update_query_expr(default_query, keep_old=False, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_must_not_vector(self, connect, collection):
        '''
        method: build query without must, with must_not.vector instead
        expected: error raised
        '''
        expr = {"must_not": default_query["bool"]["must"]}
        query = update_query_expr(default_query, keep_old=False, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_query_must_should(self, connect, collection):
        '''
        method: build query must, and with should.term
        expected: error raised
        '''
        expr = {"should": gen_default_term_expr}
        query = update_query_expr(default_query, keep_old=True, expr=expr)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)


"""
******************************************************************
#  The following cases are used to test `search` function 
#  with invalid collection_name, or invalid query expr
******************************************************************
"""

class TestSearchInvalid(object):
    """
    Test search collection with invalid collection names
    """

    @pytest.fixture(
        scope="function",
        params=gen_invalid_strs()
    )
    def get_collection_name(self, request):
        yield request.param

    @pytest.fixture(
        scope="function",
        params=gen_invalid_strs()
    )
    def get_invalid_partition(self, request):
        yield request.param

    @pytest.fixture(
        scope="function",
        params=gen_invalid_strs()
    )
    def get_invalid_field(self, request):
        yield request.param

    @pytest.fixture(
        scope="function",
        params=gen_simple_index()
    )
    def get_simple_index(self, request, connect):
        # if str(connect._cmd("mode")) == "CPU":
        #     if request.param["index_type"] in index_cpu_not_support():
        #         pytest.skip("sq8h not support in CPU mode")
        return request.param

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_with_invalid_collection(self, connect, get_collection_name):
        collection_name = get_collection_name
        with pytest.raises(Exception) as e:
            res = connect.search(collection_name, default_query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_with_invalid_partition(self, connect, collection, get_invalid_partition):
        # tag = " "
        tag = get_invalid_partition
        with pytest.raises(Exception) as e:
            res = connect.search(collection, default_query, partition_names=tag)

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_with_invalid_field_name(self, connect, collection, get_invalid_field):
        fields = [get_invalid_field]
        with pytest.raises(Exception) as e:
            res = connect.search(collection, default_query, fields=fields)

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_search_with_not_existed_field(self, connect, collection):
        fields = [gen_unique_str("field_name")]
        with pytest.raises(Exception) as e:
            res = connect.search(collection, default_query, fields=fields)

    """
    Test search collection with invalid query
    """

    @pytest.fixture(
        scope="function",
        params=gen_invalid_ints()
    )
    def get_top_k(self, request):
        yield request.param

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_search_with_invalid_top_k(self, connect, collection, get_top_k):
        '''
        target: test search function, with the wrong top_k
        method: search with top_k
        expected: raise an error, and the connection is normal
        '''
        top_k = get_top_k
        default_query["bool"]["must"][0]["vector"][field_name]["topk"] = top_k
        with pytest.raises(Exception) as e:
            res = connect.search(collection, default_query)

    """
    Test search collection with invalid search params
    """

    @pytest.fixture(
        scope="function",
        params=gen_invaild_search_params()
    )
    def get_search_params(self, request):
        yield request.param

    # 1463
    @pytest.mark.tags(CaseLabel.L2)
    def test_search_with_invalid_params(self, connect, collection, get_simple_index, get_search_params):
        '''
        target: test search function, with the wrong nprobe
        method: search with nprobe
        expected: raise an error, and the connection is normal
        '''
        search_params = get_search_params
        index_type = get_simple_index["index_type"]
        if index_type in ["FLAT"]:
            # pytest.skip("skip in FLAT index")
            pass
        if index_type != search_params["index_type"]:
            # pytest.skip("skip if index_type not matched")
            pass
        entities, ids = init_data(connect, collection, nb=1200)
        connect.create_index(collection, field_name, get_simple_index)
        connect.load_collection(collection)
        query, vecs = gen_query_vectors(field_name, entities, default_top_k, 1,
                                        search_params=search_params["search_params"])
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.L2)
    def test_search_with_invalid_params_binary(self, connect, binary_collection):
        '''
        target: test search function, with the wrong nprobe
        method: search with nprobe
        expected: raise an error, and the connection is normal
        '''
        nq = 1
        index_type = "BIN_IVF_FLAT"
        int_vectors, entities, ids = init_binary_data(connect, binary_collection)
        query_int_vectors, query_entities, tmp_ids = init_binary_data(connect, binary_collection, nb=1, insert=False)
        connect.create_index(binary_collection, binary_field_name,
                             {"index_type": index_type, "metric_type": "JACCARD", "params": {"nlist": 128}})
        connect.load_collection(binary_collection)
        query, vecs = gen_query_vectors(binary_field_name, query_entities, default_top_k, nq,
                                        search_params={"nprobe": 0}, metric_type="JACCARD")
        with pytest.raises(Exception) as e:
            res = connect.search(binary_collection, query)

    # #1464
    @pytest.mark.tags(CaseLabel.L2)
    def test_search_with_empty_params(self, connect, collection, args, get_simple_index):
        '''
        target: test search function, with empty search params
        method: search with params
        expected: raise an error, and the connection is normal
        '''
        index_type = get_simple_index["index_type"]
        if args["handler"] == "HTTP":
            pytest.skip("skip in http mode")
        if index_type == "FLAT":
            # pytest.skip("skip in FLAT index")
            pass
        entities, ids = init_data(connect, collection)
        connect.create_index(collection, field_name, get_simple_index)
        connect.load_collection(collection)
        query, vecs = gen_query_vectors(field_name, entities, default_top_k, 1, search_params={})
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_search_with_empty_vectors(self, connect, collection):
        """
        target: test search function, with empty search vectors
        method: search
        expected: raise an exception
        """
        entities, ids = init_data(connect, collection)
        assert len(ids) == default_nb
        connect.load_collection(collection)
        query, vecs = gen_query_vectors(field_name, entities, default_top_k, nq=0)
        with pytest.raises(Exception) as e:
            res = connect.search(collection, query)


class TestSearchWithExpression(object):
    @pytest.fixture(
        scope="function",
        params=[1, 10, 20],
    )
    def limit(self, request):
        yield request.param

    @pytest.fixture(
        scope="function",
        params=gen_normal_expressions(),
    )
    def expression(self, request):
        yield request.param

    @pytest.fixture(
        scope="function",
        params=[
            {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 100}},
        ]
    )
    def index_param(self, request):
        return request.param

    @pytest.fixture(
        scope="function",
    )
    def search_params(self):
        return {"metric_type": "L2", "params": {"nprobe": 10}}

    @pytest.mark.tags(CaseLabel.tags_smoke)
    def test_search_with_expression(self, connect, collection, index_param, search_params, limit, expression):
        entities, ids = init_data(connect, collection)
        assert len(ids) == default_nb
        connect.create_index(collection, default_float_vec_field_name, index_param)
        connect.load_collection(collection)
        nq = 10
        query_data = entities[2]["values"][:nq]
        res = connect.search_with_expression(collection, query_data, default_float_vec_field_name, search_params,
                                             limit, expression)
        assert len(res) == nq
        for topk_results in res:
            assert len(topk_results) <= limit


def check_id_result(result, id):
    limit_in = 5
    ids = [entity.id for entity in result]
    if len(result) >= limit_in:
        return id in ids[:limit_in]
    else:
        return id in ids
