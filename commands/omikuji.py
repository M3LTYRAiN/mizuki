import io
import disnake
from disnake.ext import commands
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from bot import bot
import math

fortune_messages = {
    "대길": [
        "오늘은 온라인에서도 좋은 기회가 올 거예요! 새로운 사람들과의 만남이 기대되네요. SNS에서 좋은 소식이 있을지도!?",
        "오늘은 당신의 온라인 활동이 빛을 발할 날! 이메일이나 DM을 체크해보세요!",
        "인싸력이 폭발하는 하루! 사람들과의 소통에서 즐거움을 찾을 수 있을 거예요.",
        "오늘 하루는 온라인에서 새로운 인연이 생길 수도 있어요. SNS에서의 활동에 주목!",
        "디지털 환경에서 큰 기회를 잡을 수 있는 날! 새로운 아이디어가 떠오를지도?",
        "새로운 온라인 플랫폼에서 활발한 활동을 해보세요. 좋은 일이 있을 거예요!",
        "야옹!"
    ],
    "길": [
        "인터넷에서 찾아낸 정보가 도움이 될 거예요. 오늘은 뭔가 기회가 찾아오는 날!",
        "디지털 환경에서 새로운 인연이 생길지도! 적극적으로 온라인 활동을 해보세요.",
        "SNS에서 발견한 아이디어가 오늘 당신에게 큰 도움이 될 거예요.",
        "오늘은 조금 더 전략적으로 온라인 활동을 해보세요. 작은 변화가 큰 성과로 이어질 거예요.",
        "온라인에서의 적극적인 커뮤니케이션이 좋은 결과를 가져올 거예요!",
        "디지털 커뮤니케이션을 통해 새로운 기회를 만들 수 있는 날이에요. 메시지를 잘 활용하세요!"
    ],
    "소길": [
        "온라인 활동에 집중하는 것이 좋지만, 너무 과하지 않게! 시간을 잘 관리하세요.",
        "디지털 기기 사용에 신경 쓰세요. 너무 많은 시간을 보내면 피로가 쌓일 수 있어요.",
        "오늘은 차분하게 온라인 활동을 하되, 오프라인에서도 소통을 잊지 마세요.",
        "운영 중인 온라인 커뮤니티나 채팅에서 작은 실수가 있을 수 있으니, 조심하세요.",
        "SNS에서의 피로감을 느낄 수 있는 하루입니다. 잠시 휴식을 취하는 것도 좋겠네요.",
        "오늘은 시간을 효율적으로 관리하는 것이 중요해요. 너무 많은 일을 벌리지 않도록!"
    ],
    "흉": [
        "오늘은 온라인에서 작은 실수가 있을 수 있어요. 발언을 조심하고, 대화에서 신중함을 유지하세요.",
        "인터넷 상에서의 갈등이 생길 수 있으니 말조심! 너무 과격한 표현은 피하는 게 좋겠어요.",
        "온라인 활동 중 오해를 살 수 있는 상황이 생길 수 있어요. 상황을 잘 파악하고 행동하세요.",
        "SNS에서의 불필요한 말다툼을 피하세요. 감정을 잘 조절해야 할 날이에요.",
        "오늘은 온라인에서의 작은 다툼이 감정적으로 영향을 줄 수 있어요. 침착함을 유지하세요.",
        "인터넷에서 비판적인 상황이 발생할 수 있으니, 온라인 상에서는 차분하게 행동하세요.",
        "오늘은 신뢰할 수 있는 정보만을 기반으로 판단해야 해요. 잘못된 정보가 문제를 일으킬 수 있습니다."
    ]
}

# 운세 번호
def get_fortune_title(fortune_level, fortune_number):
    return f"제{fortune_number}번 {fortune_level}"

# 옛날 종이 느낌의 배경 생성
def generate_paper_texture(width, height):
    paper = Image.new("RGB", (width, height), color=(255, 248, 220))  # 약간 누런색 배경

    draw = ImageDraw.Draw(paper)
    # 종이의 질감 효과를 추가하기 위해 점과 선을 조금씩 그려줍니다.
    for _ in range(500):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.line([x1, y1, x2, y2], fill=(random.randint(230, 250), random.randint(230, 250), random.randint(200, 220)), width=1)  # 약간 연하게

    # 노이즈 추가
    for _ in range(100):  # 노이즈를 좀 더 적게 추가
        x, y = random.randint(0, width), random.randint(0, height)
        draw.point((x, y), fill=(random.randint(230, 250), random.randint(230, 250), random.randint(200, 220)))  # 약간 연한 노이즈

    return paper

# 오미쿠지 이미지 생성 함수
def create_omikuji_image(fortune_level, fortune_number):
    # 이미지 크기 설정 (가로는 좁고, 세로는 길게 설정)
    width, height = 400, 900  # 세로 길이 조금 더 늘리기
    image = generate_paper_texture(width, height)  # 텍스처를 직접 생성

    draw = ImageDraw.Draw(image)

    # 빨간 테두리 위치 조정
    margin = 20
    draw.rectangle([margin, margin, width - margin, height - margin], outline="red", width=5)

    # 폰트 설정
    try:
        title_font = ImageFont.truetype("/Users/Luna/Desktop/chatzipbot/OTF/GowunBatang-Bold.ttf", 40)
        text_font = ImageFont.truetype("/Users/Luna/Desktop/chatzipbot/OTF/GowunBatang-Regular.ttf", 30)
    except IOError:
        # 기본 폰트 사용 (시스템에 따라 폰트 이름이 다를 수 있음)
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        print("경고: 지정된 폰트 파일을 찾을 수 없어 기본 폰트를 사용하는 것이다.")

    # 제목 (가로, 번호 추가)
    title = get_fortune_title(fortune_level, fortune_number)
    # 제목 텍스트 크기 계산
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width, title_height = title_bbox[2] - title_bbox[0], title_bbox[3] - title_bbox[1]

    draw.text((width // 2 - title_width // 2, 40), title, font=title_font, fill="black")  # 제목 위치 조금 위로 올리기

    # 제목과 내용 사이의 구분선
    draw.line((margin, 110, width - margin, 110), fill="red", width=5)  # 구분선 위치 조정

    # 운세 내용 (세로로 텍스트 배치)
    fortune_message = random.choice(fortune_messages[fortune_level])

    # 세로 텍스트 배치
    x, y = 50, 150
    line_width = 0
    max_width = width - 2 * margin  # 텍스트가 넘어가지 않게 제한
    current_y = y
    for char in fortune_message:
        char_bbox = draw.textbbox((0, 0), char, font=text_font)
        char_width, char_height = char_bbox[2] - char_bbox[0], char_bbox[3] - char_bbox[1]

        if current_y + char_height > height - margin - 50: # 하단 여백 추가
            x += 70
            current_y = y
            line_width = 0

        draw.text((x, current_y), char, font=text_font, fill="black")
        current_y += 35

    return image

# 운세 레벨을 확률에 맞게 생성하는 함수
def get_random_fortune_level():
    levels = ["소길", "길", "대길", "흉"]
    probabilities = [0.4, 0.4, 0.15, 0.05]  # 확률: 소길 40%, 길 40%, 대길 15%, 흉 5%
    return random.choices(levels, probabilities)[0]

# 오미쿠지 슬래시 명령어
@bot.slash_command(name="오미쿠지", description="오늘의 운세를 확인하는 것이다!")
@commands.cooldown(1, 3600, commands.BucketType.user)  # 쿨타임 설정 (1시간)
async def omikuji(ctx):
    # 운세 레벨과 번호 설정
    fortune_level = get_random_fortune_level()
    fortune_number = random.randint(1, 10)

    # 이미지 생성
    omikuji_image = create_omikuji_image(fortune_level, fortune_number)

    # 이미지 저장 및 디스코드에 전송
    with io.BytesIO() as image_binary:
        omikuji_image.save(image_binary, "PNG")
        image_binary.seek(0)
        await ctx.send(file=disnake.File(image_binary, "omikuji.png")) # 모두에게 보이도록 설정 (ephemeral=True 제거)

@omikuji.error
async def omikuji_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        retry_after_minutes = math.ceil(error.retry_after / 60)
        await ctx.send(f"{ctx.author.mention} 운세 확인은 {retry_after_minutes}분 후에 다시 시도하는 것이다!", ephemeral=True) # 본인에게만 보이도록 설정
    else:
        print(f"오미쿠지 명령어 에러: {error}")
        await ctx.send("오미쿠지를 가져오는 중에 오류가 발생한 것이다.", ephemeral=True) # 본인에게만 보이도록 설정

def setup(bot):
    bot.add_command(omikuji)