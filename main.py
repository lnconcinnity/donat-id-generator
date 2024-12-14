
import os
import dotenv
import time
import qrcode

from io import BytesIO
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import HorizontalGradiantColorMask
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

DEBUG_MODE = True

MINIMUM_MAX_RANGE_TO_LAZY_ESTIMATE_FONT_SIZE = 10
LAZY_ESTIMATE_FONT_SIZE = False
STUDENT_ID_PREFIX = "2000"
FRONT_DRAW_OPTIONS = {
    # ( position(x, y), font_size, font_style )
    "student_id_options": [ (200, 860), 30, "fonts/comic_sans_bold.ttf" ],
    "student_surname_options": [ (200, 940), 80, "fonts/arial_bold.ttf" ],
    "student_alias_options": [ (200, 1010), 70, "fonts/arial_narrow_italic.ttf" ],
}
OUT_DIR = 'out/'
TEMPLATES_DIR = 'templates/'
DONAT_QR_CODE = None

def print_debug(log):
    if DEBUG_MODE: print(log)

def dir_out(path):
    return f'{OUT_DIR}{path}'

def get_template(tag='cipher', privilege='1', extension='jpg'):
    return (f'{TEMPLATES_DIR}{tag.lower()}_{privilege}.{extension}', extension)

def draw_text(draw, text, position, color="white", font_size=20, image_width=900, horizontal_padding=0, justify="left", font_style="arial.ttf"):
    max_text_width = image_width - (2 * horizontal_padding)
    if LAZY_ESTIMATE_FONT_SIZE:
        font_size = max_text_width // len(text)
    else: # find optimal font size using binary search
        _min_size = 1
        _max_size = font_size
        while _min_size < _max_size:
            font_size = (_min_size + _max_size) // 2
            font = ImageFont.truetype(font_style, font_size)
            text_width = draw.textlength(text, font=font)
            if text_width <= max_text_width:
                _min_size = font_size + 1
            else:
                _max_size = font_size
    
    font = ImageFont.truetype(font_style, font_size)
    text_width = draw.textlength(text, font=font)
    text_x, text_y = position
    if justify == "center":
        text_x = (image_width - text_width) // 2
    elif justify == "right":
        text_x = image_width - text_width - horizontal_padding
    draw.text((text_x, text_y), text, font=font, fill=color)

def write_qr_code(text, box_size=20, version=1):
    qr = qrcode.QRCode(version=version, box_size=box_size, border=0)
    qr.add_data(text)
    qr.make()
    qr_img = qr.make_image(
        back_color=(84, 84, 84),
		fill_color=(255, 255, 255),
		image_factory=StyledPilImage,
		color_mask=HorizontalGradiantColorMask(
			back_color=(84, 84, 84),
			right_color=(255, 255, 255),
			left_color=(204, 121, 255)
		)
    )
    
    # save it temporarily, i dont want 1000 qr codes unneccessarily saved ToT
    with BytesIO() as bytes:
        qr_img.save(bytes, 'png')
        bytes.seek(0)
        image = Image.open(bytes).convert('RGBA')
    return image
        

def paste_image_to(src, dst, pos):
    dst.paste(src, pos)
    
def get_range():
    range_min = int(input("min_range: "))
    range_max = int(input("max_range: "))
    if range_min < 2 or range_max < range_min:
        print("Invalid range; Ensure min_range is greater than two (2) and max_range is greater than min_range.")
        return get_range()
    return range_min, range_max

def print_main(sheet):
    index = 0
    for row in sheet:
        index+=1
        print_debug(f'Printing row no.{index} with the content (format: name, id, subclass, privilege): {row}')
        # create a directory named after the student's id
        name, id, subclass, privilege = row
        id = "0" + (id if id.startswith(STUDENT_ID_PREFIX) else STUDENT_ID_PREFIX + id)
        
        names = name.split(" ")
        is_surname_first_format = ',' in names[0]
        names[0] = names[0][:-1] if is_surname_first_format else names[0]
        sample_length = len(names)
        surname = names[0] if is_surname_first_format else names[-1]
        
        middle_initial = None
        if sample_length > 2:
            middle_initial_position = sample_length - 1
            middle_initial = names[middle_initial_position] if '.' in names[middle_initial_position] else None
        
        if is_surname_first_format:
            first_name = " ".join(names[1:sample_length - 1]) if middle_initial else " ".join(names[1:])
        else:
            first_name = " ".join(names[:-1]) if not middle_initial else " ".join(names[1:-1])
        alias = f'{first_name}{" " + middle_initial if middle_initial else ""}'
        
        # create/modify directory
        cur_dir = dir_out(id)
        """ TODO Would probably make it so that if a folder's lifespan exceeded that of x days, renew it with a brand new one
        if os.path.exists(cur_dir):
            for filename in os.listdir(cur_dir):
                path = os.path.join(cur_dir, filename)
                if os.path.isfile(path) or os.path.islink(path):
                    os.unlink(path)
                else:
                    print(f'Illegal file found in {cur_dir}: {path}')
        """
        if not os.path.exists(cur_dir):
            Path(cur_dir).mkdir(parents=True, exist_ok=True)
        
        # draw front
        front_template, front_extension = get_template(subclass, privilege=privilege)
        with Image.open(front_template) as image:
            draw = ImageDraw.Draw(image)
            image_width, _ = image.size
            # student id
            draw_text(draw, id, FRONT_DRAW_OPTIONS["student_id_options"][0], "white", FRONT_DRAW_OPTIONS["student_id_options"][1], image_width, 0, "center", FRONT_DRAW_OPTIONS["student_id_options"][2])
            # alias
            draw_text(draw, surname.upper(), FRONT_DRAW_OPTIONS["student_surname_options"][0], "white", FRONT_DRAW_OPTIONS["student_surname_options"][1], image_width, 0, "center", FRONT_DRAW_OPTIONS["student_surname_options"][2])
            draw_text(draw, alias.upper(), FRONT_DRAW_OPTIONS["student_alias_options"][0], "white", FRONT_DRAW_OPTIONS["student_alias_options"][1], image_width, 0, "center", FRONT_DRAW_OPTIONS["student_alias_options"][2])
            
            image.save(f'{cur_dir}/front.{front_extension}')
        # draw back
        back_template, back_extension = get_template("back", privilege=privilege, extension="png")
        with Image.open(back_template) as image:
            paste_image_to(write_qr_code(id), image, (240, 304))
            paste_image_to(DONAT_QR_CODE, image, (377, 848))
            image.save(f'{cur_dir}/back.{back_extension}')

def main():
    dotenv.load_dotenv()
    # lez first get student data fr
    application_key = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    application_credentials = service_account.Credentials.from_service_account_file(application_key)
    service = build("sheets", "v4", credentials=application_credentials)
    spreadsheet_id = ""
    with open(os.getenv("GOOGLE_SPREADSHEET_ID"), 'r') as text:
        spreadsheet_id = text.readline()
    print("Specify range (min_range and max_range)")
    range_min, range_max = get_range()
    range_value = f'master!A{range_min}:D{range_max}'
    print(f'Current range to assess: {range_value}')
    if range_max > MINIMUM_MAX_RANGE_TO_LAZY_ESTIMATE_FONT_SIZE:
        global LAZY_ESTIMATE_FONT_SIZE
        LAZY_ESTIMATE_FONT_SIZE = True

    global DONAT_QR_CODE
    DONAT_QR_CODE = write_qr_code("https://www.facebook.com/OrCaDONAT/", 5, 2)
    if not os.path.exists("out"):
        Path('out').mkdir(parents=True, exist_ok=True)

    try:
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_value).execute()
        values = result.get('values', [])
        if values:
            start_time = time.time()
            print(f'Retrieved data from spreadsheet, printing IDs for students no.{range_min} to no.{range_max}')
            print_main(values)
            elapsed_time = time.time() - start_time
            print(f'Printing completed, time took: {elapsed_time}s')
        else:
            print("No data found.")
    except Exception as e:
        print(f'An error occured!\n{e}')
    
if __name__ == "__main__":
    main()