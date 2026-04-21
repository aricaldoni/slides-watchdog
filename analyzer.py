import os
import logging
from google import genai
from dotenv import load_dotenv

load_dotenv()


class PresentationAnalyzer:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.client = None
        if not self.api_key:
            logging.warning("GEMINI_API_KEY not found. Analyzer will run in mock mode.")
        else:
            self.client = genai.Client(api_key=self.api_key)

    def analyze_changes(self, diff_data):
        """
        Sends the structured diff to Gemini and returns a business summary.
        """
        if not diff_data or not diff_data.get('changes'):
            return "No significant changes detected."

        if not self.client:
            return self._mock_analysis(diff_data)

        prompt = self._build_prompt(diff_data)

        try:
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            logging.error(f"Error calling Gemini: {e}")
            return "Failed to analyze changes due to an API error."

    def _build_prompt(self, diff_data):
        """Constructs the prompt for Gemini."""
        title = diff_data.get('presentation_title', 'Unknown Deck')
        changes = diff_data.get('changes', [])
        language = os.getenv('ALERT_LANGUAGE', 'en').lower()

        diff_text = ""
        for change in changes:
            diff_text += f"- {change['slide_title']} ({change['change_type']}):\n"
            if change.get('before'):
                diff_text += f"  BEFORE: {change['before'][:500]}...\n"
            if change.get('after'):
                diff_text += f"  AFTER: {change['after'][:500]}...\n"

        prompt = f"""
You are an expert business analyst. You are monitoring a Google Slides deck titled: "{title}".
A set of changes has been detected. Your task is to provide a concise, high-level summary of what these changes mean for the business or the project.

Focus on:
1. Significant shifts in strategy, pricing, or timelines.
2. Inferred audience or purpose changes.
3. Logical conclusions about the deck's new status (e.g., "now looks like a formal proposal").

Avoid:
- Technical jargon about slide indices.
- Simply listing the changes again.

Detected Changes:
{diff_text}

Respond in plain, professional business language.
"""
        if language == 'es':
            prompt += "\nRespond entirely in Spanish.\n"
            
        return prompt

    def _mock_analysis(self, diff_data):
        """Fallback mock analysis if no API key is provided."""
        language = os.getenv('ALERT_LANGUAGE', 'en').lower()
        if language == 'es':
            return "⚠️ Agregá GEMINI_API_KEY en .env para habilitar el análisis de cambios."
        return "⚠️ Add GEMINI_API_KEY to .env to enable AI interpretation of changes."


if __name__ == "__main__":
    # Test script usage
    analyzer = PresentationAnalyzer()
    sample_diff = {
        "presentation_title": "Q3 Sales Expansion",
        "changes": [
            {
                "slide_object_id": "s3",
                "slide_title": "Pricing Strategy",
                "change_type": "text_modified",
                "before": "Standard pricing is $500 per month.",
                "after": "Standard pricing is $420 per month for the first year."
            }
        ]
    }
    print(analyzer.analyze_changes(sample_diff))
