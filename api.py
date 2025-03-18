from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from utils import fetch_news, generate_comparative_tts
import os

app = Flask(__name__)
CORS(app)


@app.route("/news", methods=["GET"])
def get_news():
    """Fetch and analyze news articles for a given company"""
    company = request.args.get("company")
    if not company:
        return jsonify({"error": "Company name is required"}), 400

    # Fetch news with the updated format
    news_data = fetch_news(company)

    return jsonify(news_data)


@app.route("/tts-final", methods=["POST"])
def text_to_speech_final():
    """Convert final sentiment analysis to Hindi speech"""
    data = request.json
    analysis = data.get("analysis", {})

    if not analysis:
        return jsonify({"error": "Analysis data is required"}), 400

    # Only generate Hindi speech for the final sentiment analysis
    audio_file = generate_comparative_tts(analysis)

    if audio_file and os.path.exists(audio_file):
        try:
            return send_file(
                audio_file,
                mimetype="audio/mpeg",
                as_attachment=True,
                download_name="final_analysis.mp3"
            )
        except Exception as e:
            return jsonify({"error": f"Error sending audio file: {str(e)}"}), 500
    else:
        return jsonify({"error": "Failed to generate speech"}), 500


if __name__ == "__main__":
    app.run(debug=True)