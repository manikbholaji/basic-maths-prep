from app import recommender


def test_recommend_field_pathways_returns_matching_field():
    profile = {
        "interests": ["coding", "math"],
        "location": "Delhi",
        "city": "Delhi",
        "class_level": "Class 11",
    }

    results = recommender.recommend_field_pathways("Engineering / Computer Science", profile)

    assert results, "Expected at least one pathway recommendation"
    assert all("engineering" in item["field"].lower() or "computer science" in item["field"].lower() for item in results), \
        "Expected all returned pathways to match the chosen field"


def test_recommend_field_pathways_humanities_uses_keywords_and_class_stage():
    profile = {
        "interests": ["history", "political science"],
        "location": "Delhi",
        "city": "Delhi",
        "class_level": "Class 12",
    }

    results = recommender.recommend_field_pathways("Humanities / Psychology / Public Policy", profile)

    assert results, "Expected at least one humanities pathway recommendation"
    assert results[0]["field"] == "Humanities / Psychology / Public Policy", "The top pathway should match the selected Humanities field"
    assert results[0]["score"] >= 8, "Humanities pathway should receive a strong score for the selected field"
    assert results[0]["class_12"].get("undergraduate_routes"), \
        "Humanities result should include undergraduate route recommendations for Class 12"


def test_recommend_field_pathways_prefers_location_matches():
    profile_with_location = {
        "interests": ["history", "policy"],
        "location": "Delhi",
        "city": "Delhi",
        "class_level": "Class 12",
    }
    profile_without_location = {
        "interests": ["history", "policy"],
        "class_level": "Class 12",
    }

    result_with_location = recommender.recommend_field_pathways("Humanities / Psychology / Public Policy", profile_with_location)
    result_without_location = recommender.recommend_field_pathways("Humanities / Psychology / Public Policy", profile_without_location)

    assert result_with_location, "Expected pathway recommendations when location is provided"
    assert result_without_location, "Expected pathway recommendations without location"
    assert result_with_location[0]["score"] >= result_without_location[0]["score"], "Location should not reduce the pathway score"
    assert result_with_location[0]["score"] > result_without_location[0]["score"], "Preferred city should increase the pathway score when it matches known institutions"


def test_recommend_field_pathways_boosts_stage_specific_routes():
    profile_no_stage = {
        "interests": ["psychology"],
        "location": "Delhi",
        "city": "Delhi",
    }
    profile_class12 = {
        "interests": ["psychology"],
        "location": "Delhi",
        "city": "Delhi",
        "class_level": "Class 12",
    }
    profile_ug = {
        "interests": ["psychology"],
        "location": "Delhi",
        "city": "Delhi",
        "class_level": "UG completion",
    }

    result_no_stage = recommender.recommend_field_pathways("Humanities / Psychology / Public Policy", profile_no_stage)
    result_class12 = recommender.recommend_field_pathways("Humanities / Psychology / Public Policy", profile_class12)
    result_ug = recommender.recommend_field_pathways("Humanities / Psychology / Public Policy", profile_ug)

    assert result_no_stage and result_class12 and result_ug, "Expected pathway recommendations for all profiles"
    assert result_class12[0]["score"] > result_no_stage[0]["score"], "Class 12 stage should increase pathway relevance"
    assert result_ug[0]["score"] > result_no_stage[0]["score"], "UG completion stage should increase pathway relevance"

def test_recommend_engineering_pathway_includes_ludhiana_institutions_and_salaries():
    profile = {
        "interests": ["coding"],
        "location": "Ludhiana",
        "city": "Ludhiana",
        "class_level": "Class 10",
    }

    results = recommender.recommend_field_pathways("Engineering / Computer Science", profile)
    assert results, "Expected engineering pathway recommendations"

    engineering_path = results[0]
    assert engineering_path.get("class_12", {}).get("top_institutions_by_city"), "Expected city-specific institution data in the engineering pathway"
    city_map = {k.lower(): v for k, v in engineering_path["class_12"]["top_institutions_by_city"].items()}
    assert "ludhiana" in city_map, "Expected Ludhiana institution recommendations"

    assert engineering_path.get("class_12", {}).get("avg_fees"), "Expected average fee estimates in the engineering pathway"
    assert engineering_path.get("class_12", {}).get("salary_overview"), "Expected salary outlook information in the engineering pathway"
