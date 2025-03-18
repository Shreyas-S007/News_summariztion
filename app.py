import streamlit as st
import requests
import json
import os
import tempfile

BACKEND_URL = "http://127.0.0.1:5000"

st.set_page_config(page_title="News Analysis", layout="wide")
st.title("News Summarization & Sentiment Analysis")

company = st.text_input("Enter Company Name", "")

if st.button("Fetch News"):
    if company:
        with st.spinner("Fetching and analyzing news articles..."):
            response = requests.get(f"{BACKEND_URL}/news?company={company}")
            if response.status_code == 200:
                data = response.json()

                # Display the data in a formatted way
                st.subheader(f"News for {data['Company']}")

                # Display articles in a cleaner format
                st.header("News Articles")

                # Use columns to display articles side by side
                cols = st.columns(2)

                for i, article in enumerate(data['Articles']):
                    with cols[i % 2]:
                        st.write(f"### Article {i + 1}: {article['Title']}")
                        st.write(f"**Summary:** {article['Summary']}")
                        st.write(f"**Sentiment:** {article['Sentiment']}")
                        st.write(f"**Topics:** {', '.join(article['Topics'])}")
                        st.write("---")

                # Display Comparative Analysis
                st.header("Comparative Analysis")

                # Coverage Differences - Detailed format
                st.subheader("Detailed Article Comparisons")

                for diff in data['Comparative Sentiment Score'].get('Coverage Differences', []):
                    with st.container():
                        st.markdown(f"#### Comparing Articles {diff.get('Articles', '')}")
                        st.markdown(f"**Content Comparison:** {diff['Comparison']}")
                        st.markdown(f"**Potential Impact:** {diff['Impact']}")
                        st.write("---")

                # Topic Overlap
                st.subheader("Topic Analysis")
                topic_overlap = data['Comparative Sentiment Score'].get('Topic Overlap', {})

                common_topics = topic_overlap.get('Common Topics', [])
                if common_topics:
                    st.write(f"**Common Topics Across Articles:** {', '.join(common_topics)}")
                else:
                    st.write("**No common topics found across articles**")

                # Final Sentiment Analysis with Hindi Audio
                st.header("Final Sentiment Analysis")
                final_sentiment = data['Comparative Sentiment Score'].get('Final Sentiment Analysis',
                                                                          'No analysis available')

                # Display the final sentiment in a prominent way
                st.markdown(f"### {final_sentiment}")

                # Generate Hindi speech for final sentiment analysis
                with st.spinner("Generating Hindi audio for final analysis..."):
                    # Create a temporary file to save the audio
                    temp_audio_file = os.path.join(tempfile.gettempdir(), "final_analysis.mp3")

                    tts_response = requests.post(
                        f"{BACKEND_URL}/tts-final",
                        json={"analysis": data['Comparative Sentiment Score']}
                    )

                    if tts_response.status_code == 200:
                        # Save the audio content to the temporary file
                        with open(temp_audio_file, "wb") as f:
                            f.write(tts_response.content)

                        # Display the audio player
                        st.audio(temp_audio_file, format="audio/mp3")
                        st.write("▶️ **Hindi Audio Summary**")
                    else:
                        st.error(f"Failed to generate Hindi speech. Error: {tts_response.text}")

                # Export JSON option
                st.header("Export Results")
                st.download_button(
                    label="Download JSON",
                    data=json.dumps(data, indent=2),
                    file_name=f"{company}_news_analysis.json",
                    mime="application/json"
                )

            else:
                st.error(f"Failed to fetch news: {response.text}")