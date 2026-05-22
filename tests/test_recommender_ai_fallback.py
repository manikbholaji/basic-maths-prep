from app import recommender


class PlainTextClient:
    def send_message(self, messages):
        return "Here is a helpful pathway, but not in JSON."


class PartialJsonClient:
    def send_message(self, messages):
        return '{"field": "Engineering / Computer Science", "summary": "Short AI summary only"}'


def test_ai_pathway_plain_text_falls_back_to_complete_template():
    profile = {
        "class_level": "Class 12",
        "city": "Ludhiana",
        "location": "Ludhiana",
        "interests": ["coding", "math"],
    }

    results = recommender.recommend_field_pathways(
        "Engineering / Computer Science",
        profile,
        ai_client=PlainTextClient(),
    )

    assert results, "Expected a pathway even when the AI returns plain text"
    item = results[0]
    assert item["field"] == "Engineering / Computer Science"
    assert item.get("class_11", {}).get("streams"), "Expected class 11 guidance from the KB template"
    assert item.get("class_12", {}).get("undergraduate_routes"), "Expected class 12 route guidance from the KB template"
    assert item.get("class_12", {}).get("top_institutions_by_city"), "Expected city-specific institutions from the KB template"
    assert item.get("career_outlook"), "Expected career outlook from the KB template"


def test_ai_pathway_partial_json_is_merged_with_template():
    profile = {
        "class_level": "Class 11",
        "city": "Delhi",
        "location": "Delhi",
        "interests": ["biology", "health"],
    }

    results = recommender.recommend_field_pathways(
        "Medical / Life Sciences",
        profile,
        ai_client=PartialJsonClient(),
    )

    assert results, "Expected a pathway even when the AI returns partial JSON"
    item = results[0]
    assert item["field"] == "Medical / Life Sciences"
    assert item.get("class_11", {}).get("subjects"), "Expected class 11 subjects after merging with the KB template"
    assert item.get("class_12", {}).get("entrance_exams"), "Expected class 12 exams after merging with the KB template"
    assert item.get("class_12", {}).get("salary_overview"), "Expected salary outlook after merging with the KB template"
