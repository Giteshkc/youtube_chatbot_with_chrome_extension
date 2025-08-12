from flask import Flask, request, jsonify
from flask_cors import CORS # Import CORS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import Chroma
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
import os
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv()

app = Flask(__name__)
# Enable CORS for all routes. In production, you might want to restrict origins.
CORS(app)

# Initialize LLM and Embeddings globally.
# Get API key from environment variables. Cloud Run will inject it.
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("Error: OPENAI_API_KEY environment variable not set.")
    # In a production app, you might raise an error or exit here.
    # For local testing, ensure it's in your .env file.

llm = ChatOpenAI(openai_api_key=openai_api_key, model="gpt-3.5-turbo") # Specify a model
embedding = OpenAIEmbeddings(openai_api_key=openai_api_key)

# Define a function to process a single video and question

def get_chatbot_response(video_id, user_question):
    ytt_api = YouTubeTranscriptApi()
    try:
        # Prioritize English, then fall back to Hindi if English not available
        transcript_list = ytt_api.fetch(video_id, languages=["en", "hi"])
        transcript = " ".join(chunk.text for chunk in transcript_list)
    except TranscriptsDisabled:
        return "Transcripts are disabled for this video, or no English/Hindi transcripts are available."
    except Exception as e:
        print(f"Error fetching transcript for video {video_id}: {str(e)}")
        return f"Error fetching transcript: {str(e)}"

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200) # Reduced overlap slightly
    # Create documents from the transcript
    chunks = splitter.create_documents([transcript])
    
    # Ensure chunking results in documents
    if not chunks:
        return "Could not split the transcript into meaningful chunks."

    vector_store = Chroma.from_documents(chunks, embedding=embedding)
    retriever = vector_store.as_retriever(search_type="mmr", search_kwargs={"k": 3})

    # Main prompt for context-aware answering
    answer_prompt = PromptTemplate(
        template="""You are a helpful AI assistant specialized in summarizing YouTube video content.
        Answer the user's question ONLY based on the provided context from the video transcript.
        If the answer cannot be found in the context, explicitly state "I don't know based on the provided video context."
        Do not make up information.

        Context:
        {context}

        Question: {question}
        """,
        input_variables=["context", "question"]
    )

    # Pre-processing prompts for spelling and grammar correction (before context retrieval)
    # Using separate chain for robustness
    spelling_correction_prompt = PromptTemplate(
        template="If there are any spelling mistakes in the following sentence, correct them. Otherwise, return the sentence as is:\nSentence: {sentence}\nCorrected Sentence:",
        input_variables=["sentence"]
    )

    grammar_correction_prompt = PromptTemplate(
        template="If there are any grammar mistakes in the following sentence, correct them. Otherwise, return the sentence as is:\nSentence: {sentence}\nCorrected Sentence:",
        input_variables=["sentence"]
    )

    parser = StrOutputParser()

    # Function to format documents for the prompt
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # Chain to process the user's question before it hits the main prompt
    # User's question goes through spelling -> grammar correction
    question_processing_chain = (
        {"sentence": RunnablePassthrough()}
        | spelling_correction_prompt
        | llm
        | parser
        | grammar_correction_prompt
        | llm
        | parser
    )

    # Main RAG (Retrieval Augmented Generation) chain
    rag_chain = RunnableParallel(
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": question_processing_chain # Use the processed question
        }
    ) | answer_prompt | llm | parser


    try:
        response = rag_chain.invoke(user_question)
        return response
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return f"Error generating response: {str(e)}"

@app.route('/ask_video', methods=['POST'])
def ask_video():
    data = request.json
    video_id = data.get('videoId')
    question = data.get('question')

    if not video_id or not question:
        return jsonify({"error": "Missing videoId or question"}), 400

    response_text = get_chatbot_response(video_id, question)
    return jsonify({"response": response_text})

if __name__ == '__main__':
    # For local development, Flask's default server is fine.
    # In production (Cloud Run), Gunicorn will run this app.
    app.run(debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5000))