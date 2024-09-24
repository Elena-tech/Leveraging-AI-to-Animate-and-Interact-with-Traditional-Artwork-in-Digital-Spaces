
from flask import current_app
from groq import Groq
import re
import json
from typing import TypedDict, Literal, List


class ArtworkFullInfo(TypedDict):
    labels: str
    short_description: str
    long_description: str
    audio_file: str
    audio_intro_file: str
    video_file: str
    intro_story: str

class ArtworkInfo(TypedDict):
    PainterName: str
    Artwork: str
    HasPerson: bool
    PersonGender: Literal['Male', 'Female', 'Unknown', 'None']


class ArtworkQuestions(TypedDict):
    QuestionNo: int
    Question: str
    
class GroqLlama:
    def __init__(self):
        self.API_KEY = current_app.config['GROQ_API_KEY']
        self.MODEL = current_app.config['GROQ_MODEL_NAME']

    def get_art(self, json_result):
        result = json.dumps(json_result, indent=2)
        get_art_prompt = (
            f"You are a museum curator with an in-depth knowledge of art. Given the following dataset of labels, descriptions, and similar images, analyze the artwork and provide information about the painter, the artwork, whether there's a person in the painting, and if so, their gender.\n\n"
            f"The dataset is as follows: {result}\n\n"
            "Use the analyze_artwork function to provide your analysis."
            "Use 'true' or 'false' (as strings) for the has_person field. Use 'None' (as a string) if there's no person in the painting for the person_gender field. "
            "Do not guess only provide 'true' if you are sure beyond reasonable doubt that there is a person in the painting.  "
        )
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "analyze_artwork",
                    "description": "Analyze the artwork and provide information about the painter, artwork, and any persons depicted",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "painter_name": {"type": "string", "description": "The full name of the painter"},
                            "artwork": {"type": "string", "description": "The name of the artwork (not a URL)"},
                            "has_person": {"type": "string", "enum": ["true", "false"], "description": "Whether there's a person in the painting"},
                            "person_gender": {"type": "string", "enum": ["Male", "Female", "Unknown", "None"], "description": "The gender of the person in the painting, or 'None' if there's no person"}
                        },
                        "required": ["painter_name", "artwork", "has_person", "person_gender"]
                    }
                }
            }
        ]
        try:
            response = self.call_groq(
                get_art_prompt,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "analyze_artwork"}}
            )
            print("GROQ RESPONSE")
            print(response)
            
            # Parse the tool call result
            tool_calls = response.choices[0].message.tool_calls
            if tool_calls:
                for tool_call in tool_calls:
                    if tool_call.function.name == "analyze_artwork":
                        function_args = json.loads(tool_call.function.arguments)
                        has_person = function_args.get('has_person', 'false').lower() == 'true'
                        person_gender = function_args.get('person_gender')
                        if person_gender == 'None':
                            person_gender = None

                        artwork_info = ArtworkInfo(
                            PainterName=function_args.get('painter_name', ''),
                            Artwork=function_args.get('artwork', ''),
                            HasPerson=has_person,
                            PersonGender=person_gender
                        )
                        
                        # Convert 'None' string to None
                        if artwork_info['PersonGender'] == 'None':
                            artwork_info['PersonGender'] = None
                        
                        return artwork_info
            
        except Exception as e:
            print(f"Error calling Groq API: {e}")
            raise RuntimeError("Failed to analyze artwork due to API error") from e

    def get_questions(self, artwork, artist) -> List[ArtworkQuestions]:
        get_questions_prompt = (
            f"You are a museum curator with an in-depth knowledge of art. Write "
            f"10 short questions that you think would have interesting answers about the painting {artwork} by {artist} and anyone depicted in the painting. "
            f"Be strict on the number of questions and do not provide questions you do not know the answer to. "
            f"Make sure there are exactly 10 questions. "
            f"Format your response as a numbered list, with each question on a new line, preceded by its number and a period."
        )

        try:
            response = self.call_groq(get_questions_prompt)
            print("GROQ RESPONSE")
            print(response)
            
            
            # Use regex to extract numbered questions
            questions = re.findall(r'\d+\.\s*(.*?)(?=\n\d+\.|\Z)', response, re.DOTALL)
            
            if len(questions) == 10:
                return [
                    ArtworkQuestions(QuestionNo=i+1, Question=q.strip())
                    for i, q in enumerate(questions)
                ]
            else:
                raise ValueError(f"Expected 10 questions, but got {len(questions)}")
        
        except Exception as e:
            print(f"Error calling Groq API: {type(e).__name__}: {str(e)}")
            if hasattr(e, 'response'):
                print(f"Response content: {getattr(e.response, 'text', '')}")
            raise RuntimeError(f"Failed to analyze artwork due to API error: {type(e).__name__}: {str(e)}") from e
    
    def get_answer(self, artwork, artist, description, user_input):
        story_prompt = (
            f"you are a the actual art piece with an indepth knowledge of art. Write "
            f"an answer to this question: {user_input} in less than 20 words "
            f"you must return just the answer text in the first person only and nothing else "
            f"The summary should be about the painting {artwork} by {artist} with a description here to give more context {description} "
            f"be strict on the word count and do not guess. "
            # <-- change here to that
        )
        print(f"Question prompt: {story_prompt}")  # Debug print

        story=self.call_groq(story_prompt)
        return story


    def get_short_history(self, artwork, artist):
        story_prompt = (
            f"you are a museum curator with an indepth knowledge of art. Write "
            f"a short summary in 200 words with one little known fact "
            f"you must return just the summary text and nothing else "
            f"The summary should be about the painting {artwork} by {artist}  "
            f"be strict on the word count and do not guess. "
            # <-- change here to that
        )
        print(f"Story prompt: {story_prompt}")  # Debug print

        story=self.call_groq(story_prompt)
        return story
    
    def get_short_description(self, artwork, artist):
        story_prompt = (
            f"you are an artist with an indepth knowledge of art techniques. Write "
            f"a short description in 50 words of what the painting shows "
            f"you must description just the summary text and nothing else "
            f"The description should be about the painting {artwork} by {artist}  "
            f"be strict on the word count and do not guess. "
            # <-- change here to that
        )
        print(f"Story prompt: {story_prompt}")  # Debug print

        story=self.call_groq(story_prompt)
        return story

    def get_long_history(self, artwork, artist):
        story_prompt = (
            f"you are a museum curator with an indepth knowledge of art. Write "
            f"A long summary of 500 words, with 5 specific facts and similar paintings that may be of interest "
            f"you must return just the summary text and nothing else "
            f"The summary should be about the painting {artwork} by {artist}  "
            f"be strict on the word count and do not guess. "
            # <-- change here to that
        )
        print(f"Story prompt: {story_prompt}")  # Debug print

        story=self.call_groq(story_prompt)
        return story
    
    def get_style(self, artist, artwork=None):
        story_prompt = (
            f"you are an artist with an indepth knowledge of art techniques. Write "
            f"a short description in 50 words of the style of the artist "
            f"you must provide the description, text and nothing else "
            f"The style should be about the artist: {artist} and should be relevant to the artwork: {artwork}  "
            f"be strict on the word count and do not guess. "
        )
        print(f"Story prompt: {story_prompt}")  # Debug print

        story=self.call_groq(story_prompt)
        return story + ' in the style of the current uploaded image'

    def call_groq(self, prompt, tools=None, tool_choice=None):
        client = Groq(api_key=self.API_KEY)
        if tools:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.MODEL,
                tools=tools,
                tool_choice=tool_choice
            )
            result=chat_completion
        else:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.MODEL
            )    
            result=chat_completion.choices[0].message.content
        return result
