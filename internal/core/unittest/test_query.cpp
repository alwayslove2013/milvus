// Copyright (C) 2019-2020 Zilliz. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software distributed under the License
// is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
// or implied. See the License for the specific language governing permissions and limitations under the License

#include <gtest/gtest.h>
#include "query/deprecated/ParserDeprecated.h"
#include "query/Expr.h"
#include "query/PlanNode.h"
#include "query/generated/ExprVisitor.h"
#include "query/generated/PlanNodeVisitor.h"
#include "test_utils/DataGen.h"
#include "query/generated/ShowPlanNodeVisitor.h"
#include "query/generated/ExecPlanNodeVisitor.h"
#include "query/PlanImpl.h"
#include "segcore/SegmentGrowingImpl.h"
#include "segcore/SegmentSealed.h"
#include "pb/schema.pb.h"

using namespace milvus;
using namespace milvus::query;
using namespace milvus::segcore;

TEST(Query, ShowExecutor) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    using namespace milvus;
    auto node = std::make_unique<FloatVectorANNS>();
    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 16, MetricType::METRIC_L2);
    int64_t num_queries = 100L;
    auto raw_data = DataGen(schema, num_queries);
    auto& info = node->search_info_;
    info.metric_type_ = MetricType::METRIC_L2;
    info.topk_ = 20;
    info.field_offset_ = FieldOffset(1000);
    node->predicate_ = std::nullopt;
    ShowPlanNodeVisitor show_visitor;
    PlanNodePtr base(node.release());
    auto res = show_visitor.call_child(*base);
    auto dup = res;
    std::cout << dup.dump(4);
}

TEST(Query, DSL) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    ShowPlanNodeVisitor shower;

    std::string dsl_string = R"(
{
    "bool": {
        "must": [
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "L2",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 10
                    }
                }
            }
        ]
    }
})";

    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 16, MetricType::METRIC_L2);

    auto plan = CreatePlan(*schema, dsl_string);
    auto res = shower.call_child(*plan->plan_node_);
    std::cout << res.dump(4) << std::endl;

    std::string dsl_string2 = R"(
{
    "bool": {
        "vector": {
            "fakevec": {
                "metric_type": "L2",
                "params": {
                    "nprobe": 10
                },
                "query": "$0",
                "topk": 10
            }
        }
    }
})";
    auto plan2 = CreatePlan(*schema, dsl_string2);
    auto res2 = shower.call_child(*plan2->plan_node_);
    std::cout << res2.dump(4) << std::endl;
    ASSERT_EQ(res, res2);
}

TEST(Query, ParsePlaceholderGroup) {
    namespace ser = milvus::proto::milvus;
    std::string dsl_string = R"(
{
    "bool": {
        "vector": {
            "fakevec": {
                "metric_type": "L2",
                "params": {
                    "nprobe": 10
                },
                "query": "$0",
                "topk": 10
            }
        }
    }
})";

    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 16, MetricType::METRIC_L2);
    auto plan = CreatePlan(*schema, dsl_string);
    int64_t num_queries = 100000;
    int dim = 16;
    auto raw_group = CreatePlaceholderGroup(num_queries, dim);
    auto blob = raw_group.SerializeAsString();
    auto placeholder = ParsePlaceholderGroup(plan.get(), blob);
}

TEST(Query, ExecWithPredicateLoader) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 16, MetricType::METRIC_L2);
    schema->AddDebugField("age", DataType::FLOAT);
    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "range": {
                    "age": {
                        "GE": -1,
                        "LT": 1
                    }
                }
            },
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "L2",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    int64_t N = 1000 * 1000;
    auto dataset = DataGen(schema, N);
    auto segment = CreateGrowingSegment(schema);
    segment->PreInsert(N);
    ColumnBasedRawData raw_data;
    raw_data.columns_ = dataset.cols_;
    raw_data.count = N;
    segment->Insert(0, N, dataset.row_ids_.data(), dataset.timestamps_.data(), raw_data);

    auto plan = CreatePlan(*schema, dsl);
    auto num_queries = 5;
    auto ph_group_raw = CreatePlaceholderGroup(num_queries, 16, 1024);
    auto ph_group = ParsePlaceholderGroup(plan.get(), ph_group_raw.SerializeAsString());
    Timestamp time = 1000000;

    auto sr = segment->Search(plan.get(), *ph_group, time);
    int topk = 5;

    Json json = SearchResultToJson(sr);
    auto ref = json::parse(R"(
[
  [
    [
      "982->0.000000",
      "25315->4.741588",
      "57893->4.758279",
      "551029->5.078479",
      "455002->5.134716"
    ],
    [
      "528353->8.740297",
      "659305->8.802286",
      "935763->9.422906",
      "794649->9.436665",
      "192031->9.832053"
    ],
    [
      "980439->3.342777",
      "433044->3.424016",
      "797884->3.663446",
      "697705->3.944479",
      "186546->4.404788"
    ],
    [
      "642941->3.753775",
      "967504->3.885163",
      "764517->4.364819",
      "332938->4.418214",
      "232724->4.574215"
    ],
    [
      "351788->4.453843",
      "410227->4.699380",
      "501497->4.805948",
      "715061->5.166959",
      "414882->5.179897"
    ]
  ]
])");
    std::cout << json.dump(2);
    ASSERT_EQ(json.dump(2), ref.dump(2));
}

TEST(Query, ExecWithPredicateSmallN) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 7, MetricType::METRIC_L2);
    schema->AddDebugField("age", DataType::FLOAT);
    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "range": {
                    "age": {
                        "GE": -1,
                        "LT": 1
                    }
                }
            },
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "L2",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    int64_t N = 177;
    auto dataset = DataGen(schema, N);
    auto segment = CreateGrowingSegment(schema);
    segment->PreInsert(N);
    segment->Insert(0, N, dataset.row_ids_.data(), dataset.timestamps_.data(), dataset.raw_);

    auto plan = CreatePlan(*schema, dsl);
    auto num_queries = 5;
    auto ph_group_raw = CreatePlaceholderGroup(num_queries, 7, 1024);
    auto ph_group = ParsePlaceholderGroup(plan.get(), ph_group_raw.SerializeAsString());
    Timestamp time = 1000000;

    auto sr = segment->Search(plan.get(), *ph_group, time);
    int topk = 5;

    Json json = SearchResultToJson(sr);
    std::cout << json.dump(2);
}

TEST(Query, ExecWithPredicate) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 16, MetricType::METRIC_L2);
    schema->AddDebugField("age", DataType::FLOAT);
    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "range": {
                    "age": {
                        "GE": -1,
                        "LT": 1
                    }
                }
            },
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "L2",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    int64_t N = 1000 * 1000;
    auto dataset = DataGen(schema, N);
    auto segment = CreateGrowingSegment(schema);
    segment->PreInsert(N);
    segment->Insert(0, N, dataset.row_ids_.data(), dataset.timestamps_.data(), dataset.raw_);

    auto plan = CreatePlan(*schema, dsl);
    auto num_queries = 5;
    auto ph_group_raw = CreatePlaceholderGroup(num_queries, 16, 1024);
    auto ph_group = ParsePlaceholderGroup(plan.get(), ph_group_raw.SerializeAsString());
    Timestamp time = 1000000;

    auto sr = segment->Search(plan.get(), *ph_group, time);
    int topk = 5;

    Json json = SearchResultToJson(sr);
    auto ref = json::parse(R"(
[
  [
    [
      "982->0.000000",
      "25315->4.741588",
      "57893->4.758279",
      "551029->5.078479",
      "455002->5.134716"
    ],
    [
      "528353->8.740297",
      "659305->8.802286",
      "935763->9.422906",
      "794649->9.436665",
      "192031->9.832053"
    ],
    [
      "980439->3.342777",
      "433044->3.424016",
      "797884->3.663446",
      "697705->3.944479",
      "186546->4.404788"
    ],
    [
      "642941->3.753775",
      "967504->3.885163",
      "764517->4.364819",
      "332938->4.418214",
      "232724->4.574215"
    ],
    [
      "351788->4.453843",
      "410227->4.699380",
      "501497->4.805948",
      "715061->5.166959",
      "414882->5.179897"
    ]
  ]
])");
    std::cout << json.dump(2);
    ASSERT_EQ(json.dump(2), ref.dump(2));
}

TEST(Query, ExecTerm) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 16, MetricType::METRIC_L2);
    schema->AddDebugField("age", DataType::FLOAT);
    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "term": {
                    "age": {
                        "values": []
                    }
                }
            },
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "L2",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    int64_t N = 1000 * 1000;
    auto dataset = DataGen(schema, N);
    auto segment = CreateGrowingSegment(schema);
    segment->PreInsert(N);
    segment->Insert(0, N, dataset.row_ids_.data(), dataset.timestamps_.data(), dataset.raw_);

    auto plan = CreatePlan(*schema, dsl);
    auto num_queries = 3;
    auto ph_group_raw = CreatePlaceholderGroup(num_queries, 16, 1024);
    auto ph_group = ParsePlaceholderGroup(plan.get(), ph_group_raw.SerializeAsString());
    SearchResult sr;
    Timestamp time = 1000000;

    sr = segment->Search(plan.get(), *ph_group, time);
    std::vector<std::vector<std::string>> results;
    int topk = 5;
    auto json = SearchResultToJson(sr);
    ASSERT_EQ(sr.num_queries_, num_queries);
    ASSERT_EQ(sr.topk_, topk);
    // for(auto x: )
}

TEST(Query, ExecEmpty) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("age", DataType::FLOAT);
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 16, MetricType::METRIC_L2);
    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "L2",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    int64_t N = 1000 * 1000;
    auto segment = CreateGrowingSegment(schema);
    auto plan = CreatePlan(*schema, dsl);
    auto num_queries = 5;
    auto ph_group_raw = CreatePlaceholderGroup(num_queries, 16, 1024);
    auto ph_group = ParsePlaceholderGroup(plan.get(), ph_group_raw.SerializeAsString());
    Timestamp time = 1000000;

    auto sr = segment->Search(plan.get(), *ph_group, time);
    std::cout << SearchResultToJson(sr);

    for (auto i : sr.internal_seg_offsets_) {
        ASSERT_EQ(i, -1);
    }

    for (auto v : sr.result_distances_) {
        ASSERT_EQ(v, std::numeric_limits<float>::max());
    }
}

TEST(Query, ExecWithoutPredicateFlat) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 16, std::nullopt);
    schema->AddDebugField("age", DataType::FLOAT);
    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "L2",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    auto plan = CreatePlan(*schema, dsl);
    int64_t N = 1000 * 1000;
    auto dataset = DataGen(schema, N);
    auto segment = CreateGrowingSegment(schema);
    segment->PreInsert(N);
    segment->Insert(0, N, dataset.row_ids_.data(), dataset.timestamps_.data(), dataset.raw_);

    auto num_queries = 5;
    auto ph_group_raw = CreatePlaceholderGroup(num_queries, 16, 1024);
    auto ph_group = ParsePlaceholderGroup(plan.get(), ph_group_raw.SerializeAsString());
    SearchResult sr;
    Timestamp time = 1000000;

    sr = segment->Search(plan.get(), *ph_group, time);
    std::vector<std::vector<std::string>> results;
    int topk = 5;
    auto json = SearchResultToJson(sr);
    std::cout << json.dump(2);
}

TEST(Query, ExecWithoutPredicate) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_FLOAT, 16, MetricType::METRIC_L2);
    schema->AddDebugField("age", DataType::FLOAT);
    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "L2",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    auto plan = CreatePlan(*schema, dsl);
    int64_t N = 1000 * 1000;
    auto dataset = DataGen(schema, N);
    auto segment = CreateGrowingSegment(schema);
    segment->PreInsert(N);
    segment->Insert(0, N, dataset.row_ids_.data(), dataset.timestamps_.data(), dataset.raw_);

    auto num_queries = 5;
    auto ph_group_raw = CreatePlaceholderGroup(num_queries, 16, 1024);
    auto ph_group = ParsePlaceholderGroup(plan.get(), ph_group_raw.SerializeAsString());
    SearchResult sr;
    Timestamp time = 1000000;

    sr = segment->Search(plan.get(), *ph_group, time);
    std::vector<std::vector<std::string>> results;
    int topk = 5;
    auto json = SearchResultToJson(sr);
    auto ref = json::parse(R"(
[
  [
    [
      "982->0.000000",
      "25315->4.741588",
      "57893->4.758279",
      "694663->4.980466",
      "551029->5.078479"
    ],
    [
      "559507->7.956653",
      "871836->8.694542",
      "528353->8.740297",
      "659305->8.802286",
      "516137->8.935913"
    ],
    [
      "980439->3.342777",
      "433044->3.424016",
      "527556->3.487235",
      "797884->3.663446",
      "814805->3.782786"
    ],
    [
      "642941->3.753775",
      "967504->3.885163",
      "177960->4.339530",
      "764517->4.364819",
      "841079->4.403300"
    ],
    [
      "688614->4.259011",
      "351788->4.453843",
      "452698->4.473838",
      "410227->4.699380",
      "501497->4.805948"
    ]
  ]
]
)");
    std::cout << json.dump(2);
    ASSERT_EQ(json.dump(2), ref.dump(2));
}

TEST(Indexing, InnerProduct) {
    int64_t N = 100000;
    constexpr auto dim = 16;
    constexpr auto topk = 10;
    auto num_queries = 5;
    auto schema = std::make_shared<Schema>();
    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "vector": {
                    "normalized": {
                        "metric_type": "IP",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    schema->AddDebugField("normalized", DataType::VECTOR_FLOAT, dim, MetricType::METRIC_INNER_PRODUCT);
    auto dataset = DataGen(schema, N);
    auto segment = CreateGrowingSegment(schema);
    auto plan = CreatePlan(*schema, dsl);
    segment->PreInsert(N);
    segment->Insert(0, N, dataset.row_ids_.data(), dataset.timestamps_.data(), dataset.raw_);
    auto col = dataset.get_col<float>(0);

    auto ph_group_raw = CreatePlaceholderGroupFromBlob(num_queries, 16, col.data());
    auto ph_group = ParsePlaceholderGroup(plan.get(), ph_group_raw.SerializeAsString());
    Timestamp ts = N * 2;
    SearchResult sr;
    sr = segment->Search(plan.get(), *ph_group, ts);
    std::cout << SearchResultToJson(sr).dump(2);
}

TEST(Query, FillSegment) {
    namespace pb = milvus::proto;
    pb::schema::CollectionSchema proto;
    proto.set_name("col");
    proto.set_description("asdfhsalkgfhsadg");
    proto.set_autoid(false);
    auto dim = 16;

    {
        auto field = proto.add_fields();
        field->set_name("fakevec");
        field->set_is_primary_key(false);
        field->set_description("asdgfsagf");
        field->set_fieldid(100);
        field->set_data_type(pb::schema::DataType::FloatVector);
        auto param = field->add_type_params();
        param->set_key("dim");
        param->set_value("16");
        auto iparam = field->add_index_params();
        iparam->set_key("metric_type");
        iparam->set_value("L2");
    }

    {
        auto field = proto.add_fields();
        field->set_name("the_key");
        field->set_fieldid(101);
        field->set_is_primary_key(true);
        field->set_description("asdgfsagf");
        field->set_data_type(pb::schema::DataType::Int64);
    }

    {
        auto field = proto.add_fields();
        field->set_name("the_value");
        field->set_fieldid(102);
        field->set_is_primary_key(false);
        field->set_description("asdgfsagf");
        field->set_data_type(pb::schema::DataType::Int32);
    }

    auto schema = Schema::ParseFrom(proto);

    // dispatch here
    int N = 100000;
    auto dataset = DataGen(schema, N);
    const auto std_vec = dataset.get_col<int64_t>(1);
    const auto std_vfloat_vec = dataset.get_col<float>(0);
    const auto std_i32_vec = dataset.get_col<int32_t>(2);

    std::vector<std::unique_ptr<SegmentInternalInterface>> segments;
    segments.emplace_back([&] {
        auto segment = CreateGrowingSegment(schema);
        segment->PreInsert(N);
        segment->Insert(0, N, dataset.row_ids_.data(), dataset.timestamps_.data(), dataset.raw_);
        return segment;
    }());
    segments.emplace_back([&] {
        auto segment = CreateSealedSegment(schema);
        SealedLoader(dataset, *segment);
        // auto indexing = GenIndexing(N, dim, std_vfloat_vec.data());

        // LoadIndexInfo info;
        // auto field_offset = schema->get_offset(FieldName("fakevec"));
        // auto& meta = schema->operator[](field_offset);

        // info.field_id = meta.get_id().get();
        // info.field_name = meta.get_name().get();
        // info.index_params["metric_type"] = "L2";
        // info.index = indexing;

        // segment->LoadIndex(info);
        return segment;
    }());

    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "L2",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    auto plan = CreatePlan(*schema, dsl);
    auto ph_proto = CreatePlaceholderGroup(10, 16, 443);
    auto ph = ParsePlaceholderGroup(plan.get(), ph_proto.SerializeAsString());
    Timestamp ts = N * 2UL;
    auto topk = 5;
    auto num_queries = 10;

    for (auto& segment : segments) {
        plan->target_entries_.clear();
        plan->target_entries_.push_back(schema->get_offset(FieldName("fakevec")));
        plan->target_entries_.push_back(schema->get_offset(FieldName("the_value")));
        SearchResult result = segment->Search(plan.get(), *ph, ts);
        // std::cout << SearchResultToJson(result).dump(2);
        result.result_offsets_.resize(topk * num_queries);
        segment->FillTargetEntry(plan.get(), result);

        auto ans = result.row_data_;
        ASSERT_EQ(ans.size(), topk * num_queries);
        int64_t std_index = 0;

        for (auto& vec : ans) {
            ASSERT_EQ(vec.size(), sizeof(int64_t) + sizeof(float) * dim + sizeof(int32_t));
            int64_t val;
            memcpy(&val, vec.data(), sizeof(int64_t));

            auto internal_offset = result.internal_seg_offsets_[std_index];
            auto std_val = std_vec[internal_offset];
            auto std_i32 = std_i32_vec[internal_offset];
            std::vector<float> std_vfloat(dim);
            std::copy_n(std_vfloat_vec.begin() + dim * internal_offset, dim, std_vfloat.begin());

            ASSERT_EQ(val, std_val) << "io:" << internal_offset;
            if (val != -1) {
                std::vector<float> vfloat(dim);
                int i32;
                memcpy(vfloat.data(), vec.data() + sizeof(int64_t), dim * sizeof(float));
                memcpy(&i32, vec.data() + sizeof(int64_t) + dim * sizeof(float), sizeof(int32_t));
                ASSERT_EQ(vfloat, std_vfloat) << std_index;
                ASSERT_EQ(i32, std_i32) << std_index;
            }
            ++std_index;
        }
    }
}

TEST(Query, ExecWithPredicateBinary) {
    using namespace milvus::query;
    using namespace milvus::segcore;
    auto schema = std::make_shared<Schema>();
    schema->AddDebugField("fakevec", DataType::VECTOR_BINARY, 512, MetricType::METRIC_Jaccard);
    schema->AddDebugField("age", DataType::FLOAT);
    std::string dsl = R"({
        "bool": {
            "must": [
            {
                "range": {
                    "age": {
                        "GE": -1,
                        "LT": 1
                    }
                }
            },
            {
                "vector": {
                    "fakevec": {
                        "metric_type": "Jaccard",
                        "params": {
                            "nprobe": 10
                        },
                        "query": "$0",
                        "topk": 5
                    }
                }
            }
            ]
        }
    })";
    int64_t N = 1000 * 1000;
    auto dataset = DataGen(schema, N);
    auto segment = CreateGrowingSegment(schema);
    segment->PreInsert(N);
    segment->Insert(0, N, dataset.row_ids_.data(), dataset.timestamps_.data(), dataset.raw_);
    auto vec_ptr = dataset.get_col<uint8_t>(0);

    auto plan = CreatePlan(*schema, dsl);
    auto num_queries = 5;
    auto ph_group_raw = CreateBinaryPlaceholderGroupFromBlob(num_queries, 512, vec_ptr.data() + 1024 * 512 / 8);
    auto ph_group = ParsePlaceholderGroup(plan.get(), ph_group_raw.SerializeAsString());
    SearchResult sr;
    Timestamp time = 1000000;

    sr = segment->Search(plan.get(), *ph_group, time);
    int topk = 5;

    Json json = SearchResultToJson(sr);
    std::cout << json.dump(2);
    // ASSERT_EQ(json.dump(2), ref.dump(2));
}
