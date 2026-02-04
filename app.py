import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import requests
import urllib.request
import os
import replicate
import fal_client
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]
os.environ["FAL_KEY"] = st.secrets["FAL_KEY"]
API_KEY = st.secrets["google_api_key"]


def call_web_fonts_api(font_query):
    if len(font_query) == 1:
        url = "https://webfonts.googleapis.com/v1/webfonts"
        params = {
            "family": font_query[0],
            "sort": "SORT_UNDEFINED",
            "key": API_KEY
        }
        headers = {
            "Accept": "application/json"
        }
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        a = response.json()
        list_a = [f"{a["items"][0]["files"]["regular"]}"]
        return list_a
    else:
        url = "https://webfonts.googleapis.com/v1/webfonts"
        params = {
            "family": [font_query[0], font_query[1]],
            "sort": "SORT_UNDEFINED",
            "key": API_KEY
        }
        headers = {
            "Accept": "application/json"
        }
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        a = response.json()
        if len(a["items"]) == 2:
            first_response = a["items"][0]["files"]["regular"]
            second_response = a["items"][1]["files"]["regular"]
            return [f"{first_response}", f"{second_response}"]
        else:
            first_response = a["items"][0]["files"]["regular"]
            return [f"{first_response}"]


def convert_ttf_to_image(ttf_url, identifier):
    FONT_PATH = "font.ttf"
    OUTPUT_PNG = f"font_preview_{identifier}.png"
    TEXT = """ABCDEFGHIJKLMNOP

    abcdefghijklmnop

    0123456789

    !"#$%&'()*+,-./:
    ;<=>?@[\]^_`{|}~

    """
    FONT_SIZE = 80
    IMG_SIZE = (800, 300)
    BG_COLOR = (255, 255, 255)
    TEXT_COLOR = (0, 0, 0)
    urllib.request.urlretrieve(ttf_url, FONT_PATH)
    print("Font downloaded:", FONT_PATH)
    img = Image.new("RGB", IMG_SIZE, BG_COLOR)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    bbox = draw.textbbox((0, 0), TEXT, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (IMG_SIZE[0] - text_width) // 2
    y = (IMG_SIZE[1] - text_height) // 2
    draw.text((x, y), TEXT, fill=TEXT_COLOR, font=font)
    img.save(OUTPUT_PNG)
    return OUTPUT_PNG


def run_replicate(user_prompt, selected_aspect_ratio, number_of_query, text_of_font, font_query):
    if number_of_query == 2:
        result_from_web_font_api = call_web_fonts_api(font_query)
        if len(result_from_web_font_api) == 2:
            input_data = {
                "resolution": "1K",
                "instruction": user_prompt,
                "init_images": [],
                "aspect_ratio": selected_aspect_ratio,
                "enhance_prompt": False,
                "font_urls": [result_from_web_font_api[0], result_from_web_font_api[1]],
                "output_format": "png",
                "font_texts": [text_of_font[0], text_of_font[1]]
            }
            image_riverflow = replicate.run("sourceful/riverflow-2.0-pro", input=input_data)
            print(image_riverflow)
            out_path = "river_flow.png"
            for item in image_riverflow:
                with open(out_path, "wb") as file:
                    file.write(item.read())
            return {"both_fonts_correct": True, "output_image_path": out_path}
        else:
            input_data = {
                "resolution": "1K",
                "instruction": user_prompt,
                "aspect_ratio": selected_aspect_ratio,
                "enhance_prompt": False,
                "font_urls": [result_from_web_font_api[0]],
                "output_format": "png",
                "font_texts": [text_of_font[0]]
            }
            image_riverflow = replicate.run("sourceful/riverflow-2.0-pro", input=input_data)
            out_path = "river_flow.png"
            for item in image_riverflow:
                with open(out_path, "wb") as file:
                    file.write(item.read())
            return {"both_fonts_correct": False, "output_image_path": out_path, "message": "One of yours font spelling"
                                                                                           "is wrong"}
    else:
        result_from_web_font_api = call_web_fonts_api(font_query)
        input_data = {
            "resolution": "1K",
            "instruction": user_prompt,
            "aspect_ratio": selected_aspect_ratio,
            "enhance_prompt": False,
            "font_urls": [result_from_web_font_api[0]],
            "output_format": "png",
            "font_texts": [text_of_font[0]]
        }
        image_riverflow = replicate.run("sourceful/riverflow-2.0-pro", input=input_data)
        out_path = "river_flow.png"
        for item in image_riverflow:
            with open(out_path, "wb") as file:
                file.write(item.read())
        return {"both_fonts_correct": True, "output_image_path": out_path}


def on_queue_update(update):
    if isinstance(update, fal_client.InProgress):
        for log in update.logs:
            print(log["message"])


def call_nano_banana(user_prompt, selected_aspect_ratio, number_of_query, text_of_font, font_query):
    result_from_web_font_api = call_web_fonts_api(font_query)
    if number_of_query == 2:
        if len(result_from_web_font_api) == 2:
            user_prompt_m = {
                "instruction": user_prompt,
                "fonts_and_text_instruction": f"For {text_of_font[0]} use font from Image 1 and "
                                              f"for {text_of_font[1]} use font from Image 2"
            }
            first_image_png = convert_ttf_to_image(result_from_web_font_api[0], "first")
            first_image_url = fal_client.upload_file(first_image_png)
            second_image_png = convert_ttf_to_image(result_from_web_font_api[1], "second")
            second_image_url = fal_client.upload_file(second_image_png)
            result = fal_client.subscribe(
                "fal-ai/nano-banana-pro/edit",
                arguments={
                    "prompt": str(user_prompt_m),
                    "image_urls": [first_image_url, second_image_url],
                    "aspect_ratio": selected_aspect_ratio,
                    "output_format": "png",
                    "resolution": "1K"
                },
                with_logs=False,
                on_queue_update=on_queue_update, )
            final_image = result["images"][0]["url"]
            nb_output_path = "NB.png"
            urllib.request.urlretrieve(final_image, nb_output_path)
            os.remove(first_image_png)
            os.remove(second_image_png)
            return {"both_fonts_correct": True, "output_image_path": nb_output_path}
        else:
            user_prompt_m = {
                "instruction": user_prompt,
                "fonts_and_text_instruction": f"For {text_of_font[0]} use font from Image 1"
            }
            first_image_png = convert_ttf_to_image(result_from_web_font_api[0], "first")
            first_image_url = fal_client.upload_file(first_image_png)
            result = fal_client.subscribe(
                "fal-ai/nano-banana-pro/edit",
                arguments={
                    "prompt": str(user_prompt_m),
                    "image_urls": [first_image_url],
                    "aspect_ratio": selected_aspect_ratio,
                    "output_format": "png",
                    "resolution": "1K",
                },
                with_logs=False,
                on_queue_update=on_queue_update,
            )
            final_image = result["images"][0]["url"]
            nb_output_path = "NB.png"
            urllib.request.urlretrieve(final_image, nb_output_path)
            os.remove(first_image_png)
            return {"both_fonts_correct": False, "output_image_path": nb_output_path, "message": "One of yours font "
                                                                                                 "spelling"
                                                                                                 "is wrong"}
    else:
        user_prompt_m = {
            "instruction": user_prompt,
            "fonts_and_text_instruction": f"For {text_of_font[0]} use font from Image 1"
        }
        first_image_png = convert_ttf_to_image(result_from_web_font_api[0], "first")
        first_image_url = fal_client.upload_file(first_image_png)
        result = fal_client.subscribe(
            "fal-ai/nano-banana-pro/edit",
            arguments={
                "prompt": str(user_prompt_m),
                "image_urls": [first_image_url],
                "aspect_ratio": selected_aspect_ratio,
                "output_format": "png",
                "resolution": "1K"
            },
            with_logs=False,
            on_queue_update=on_queue_update,
        )
        final_image = result["images"][0]["url"]
        nb_output_path = "NB.png"
        urllib.request.urlretrieve(final_image, nb_output_path)
        os.remove(first_image_png)
        return {"both_fonts_correct": True, "output_image_path": nb_output_path}


st.set_page_config(layout="wide")
st.title("RiverFlow Vs Caimera NB Agent")

with st.sidebar:
    st.header("Inputs")
    prompt = st.text_area("Prompt", height=120)
    number_of_fonts = int(st.number_input("Input number of fonts (max 2)"))
    font_name_first = st.text_input("Font 01 (name)")
    font_name_second = st.text_input("Font 02 (name)")
    text_font_one = st.text_area("Text for font 01", height=80)
    text_font_second = st.text_area("Text for font 02", height=80)
    aspect_ratio = st.text_input("Aspect Ratio (e.g. 3:4, 1:1)", value="1:1")
    run = st.button("🚀 Run")

if run:
    text_of_font = [text_font_one, text_font_second]
    font_query = [font_name_first, font_name_second]

    # Create columns for side-by-side display
    col1, col2 = st.columns(2)

    # Create placeholders for dynamic updates
    with col1:
        placeholder_replicate = st.empty()
        image_replicate = st.empty()
    with col2:
        placeholder_nano = st.empty()
        image_nano = st.empty()

    # Show initial loading state
    placeholder_replicate.info("🔄 RiverFlow 2.0 - Generating...")
    placeholder_nano.info("🔄 Caimera NB Agent - Generating...")

    # Store results
    img1 = None
    img2 = None

    # Execute both API calls in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tasks
        future_replicate = executor.submit(
            run_replicate,
            prompt,
            aspect_ratio,
            number_of_fonts,
            text_of_font,
            font_query
        )
        future_nano_banana = executor.submit(
            call_nano_banana,
            prompt,
            aspect_ratio,
            number_of_fonts,
            text_of_font,
            font_query
        )

        # Create a dictionary to track futures
        futures = {
            future_replicate: ('replicate', placeholder_replicate, image_replicate),
            future_nano_banana: ('nano', placeholder_nano, image_nano)
        }

        # Process results as they complete
        for future in as_completed(futures):
            api_name, placeholder, image_placeholder = futures[future]

            try:
                result = future.result()

                if api_name == 'replicate':
                    img1 = result
                    placeholder.success("✅ RiverFlow 2.0 - Complete!")
                    if not result["both_fonts_correct"]:
                        image_placeholder.text(result["message"])
                    image_placeholder.image(
                        result["output_image_path"],
                        caption="RiverFlow 2.0 Image",
                        use_container_width=True
                    )
                else:  # nano
                    img2 = result
                    placeholder.success("✅ Caimera NB Agent - Complete!")
                    image_placeholder.image(
                        result["output_image_path"],
                        caption="Caimera NB Agent",
                        use_container_width=True
                    )
            except Exception as e:
                if api_name == 'replicate':
                    placeholder.error(f"❌ RiverFlow 2.0 - Error: {str(e)}")
                else:
                    placeholder.error(f"❌ Caimera NB Agent - Error: {str(e)}")