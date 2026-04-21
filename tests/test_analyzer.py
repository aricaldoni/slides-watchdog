import pytest
from analyzer import PresentationAnalyzer

def test_prompt_building():
    analyzer = PresentationAnalyzer(api_key="mock_key")
    sample_diff = {
        "presentation_title": "Test Deck",
        "changes": [
            {
                "slide_index": 0,
                "slide_title": "Slide 1",
                "change_type": "text_modified",
                "before": "Hello",
                "after": "World"
            }
        ]
    }
    prompt = analyzer._build_prompt(sample_diff)
    assert "Test Deck" in prompt
    assert "Slide 1" in prompt
    assert "Hello" in prompt
    assert "World" in prompt

def test_mock_analysis():
    analyzer = PresentationAnalyzer(api_key=None)
    sample_diff = {
        "presentation_title": "Test Deck",
        "changes": [{"slide_index": 0, "slide_title": "Slide 1", "change_type": "slide_added", "before": None, "after": "Content"}]
    }
    result = analyzer.analyze_changes(sample_diff)
    assert "⚠️" in result
    assert "GEMINI_API_KEY" in result
