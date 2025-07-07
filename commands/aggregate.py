from disnake.ext import commands
import disnake
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import datetime
import pytz
from collections import Counter
from bot import bot, server_roles, server_excluded_roles, get_messages_in_period, save_last_aggregate_date, update_role_streak, get_role_streak, reset_chat_counts, server_chat_counts
import random
import math
from commands.role_color import restore_role_original_color
import os
import sys

# 여러 환경에서 작동하는 경로 탐색 로직
def find_resource_dir():
    # 우선 현재 파일 기준 상대 경로 시도
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 가능한 경로 후보들
    candidates = [
        base_dir,                # 일반적인 상대 경로
        "/app",                  # Docker 컨테이너 기본 경로
        os.getcwd(),             # 현재 작업 디렉토리
    ]
    
    # 각 후보 경로에서 필요한 디렉토리가 있는지 확인
    for path in candidates:
        if os.path.exists(os.path.join(path, "OTF")) and os.path.exists(os.path.join(path, "im")):
            return path
    
    # 기본값으로 첫번째 후보 반환
    return candidates[0]

# 리소스 디렉토리 경로 찾기
BASE_DIR = find_resource_dir()
FONT_DIR = os.path.join(BASE_DIR, 'OTF')
IMAGE_DIR = os.path.join(BASE_DIR, 'im')

# 폰트 및 이미지 경로
MAIN_FONT_PATH = os.path.join(FONT_DIR, 'ONE Mobile POP.ttf')
FALLBACK_FONT_PATH = os.path.join(FONT_DIR, '夏蝉丸ゴシック.ttf')
WHOLE_IMAGE_PATH = os.path.join(IMAGE_DIR, 'whole.png')

# 디버깅 정보 출력
print(f"[🔍 경로 정보]")
print(f"현재 작업 폴더: {os.getcwd()}")
print(f"사용 중인 기본 디렉토리: {BASE_DIR}")
print(f"폰트 디렉토리: {FONT_DIR} (존재: {os.path.exists(FONT_DIR)})")
print(f"이미지 디렉토리: {IMAGE_DIR} (존재: {os.path.exists(IMAGE_DIR)})")
print(f"Python 모듈 경로: {sys.path}")

@bot.slash_command(name="집계", description="서버에서 가장 채팅을 많이 친 6명을 집계하는 것이다.")
@commands.has_permissions(administrator=True)
async def 집계(inter: disnake.ApplicationCommandInteraction, start_date: str, end_date: str):
    try:
        # 초기 응답 지연 (15초 타임아웃)
        await inter.response.defer(ephemeral=False, with_message=True)

        guild_id = inter.guild.id
        
        if guild_id not in server_roles:
            await inter.edit_original_response(content="❌ 역할이 설정되지 않았습니다. /역할설정 명령어를 사용하는 것이다.")
            return

        # KST 시간대 설정
        kst = pytz.timezone('Asia/Seoul')
        today = datetime.datetime.now(kst)

        # 't' 입력 처리
        if start_date.lower() == 't':
            start_date = today.strftime("%Y%m%d")
        if end_date.lower() == 't':
            end_date = today.strftime("%Y%m%d")

        try:
            # 날짜 변환
            start = datetime.datetime.strptime(start_date, "%Y%m%d")
            end = datetime.datetime.strptime(end_date, "%Y%m%d")
            
            start_date = kst.localize(start.replace(hour=0, minute=0, second=0))
            end_date = kst.localize(end.replace(hour=23, minute=59, second=59))
            
            start_date_utc = start_date.astimezone(pytz.UTC)
            end_date_utc = end_date.astimezone(pytz.UTC)
        except ValueError:
            await inter.edit_original_response(
                content="❌ 날짜 형식이 잘못되었습니다. yyyyMMdd 형식 또는 't'로 입력하는 것이다."
            )
            return

        # 진행 상황 알림
        await inter.edit_original_response(content="메시지를 조회 중인 것이다... ⏳")

        # 메시지 조회
        messages = get_messages_in_period(guild_id, start_date_utc, end_date_utc)
        if not messages:
            await inter.edit_original_response(
                content=f"❌ 이 기간 동안 채팅 데이터가 없는 것이다.\n"
                f"검색 기간: {start_date.strftime('%Y-%m-%d %H:%M')} ~ {end_date.strftime('%Y-%m-%d %H:%M')}"
            )
            return

        # 채팅 카운트 계산
        chat_counts = Counter(msg['user_id'] for msg in messages)
        excluded_roles = server_excluded_roles.get(guild_id, [])
        excluded_members = {member.id for member in inter.guild.members
                            if any(role.id in excluded_roles for role in member.roles)}
        
        top_chatters = [(user_id, count) for user_id, count in chat_counts.most_common()
                        if user_id not in excluded_members][:6]

        if not top_chatters:
            await inter.edit_original_response(content="❌ 집계할 수 있는 사용자가 없는 것이다.")
            return

        # 역할 업데이트
        first_role = disnake.utils.get(inter.guild.roles, id=server_roles[guild_id]["first"])
        other_role = disnake.utils.get(inter.guild.roles, id=server_roles[guild_id]["other"])

        if not first_role or not other_role:
            await inter.edit_original_response(content="❌ 설정된 역할을 찾을 수 없는 것이다.")
            return

        # 순위권 사용자 목록 (ID만 추출)
        top_user_ids = [user_id for user_id, _ in top_chatters]
        
        # 새로운 부분: 기존에 역할이 있었지만 이번에 순위권에서 벗어난 사용자들의 연속 기록 초기화
        for member in inter.guild.members:
            if (first_role in member.roles or other_role in member.roles) and member.id not in top_user_ids:
                # 순위권 밖으로 떨어진 사용자의 연속 기록 초기화
                from bot import reset_user_role_streak
                reset_user_role_streak(guild_id, member.id)
                print(f"[집계] 사용자 {member.id}({member.display_name})의 연속 기록 초기화 (순위권 제외)")

        # 기존 역할 제거
        for member in inter.guild.members:
            if first_role in member.roles or other_role in member.roles:
                await member.remove_roles(first_role, other_role)

        # 1등 역할 원래 색상으로 복원 (추가된 부분)
        original_color = restore_role_original_color(inter.guild, first_role)
        if original_color:
            await first_role.edit(color=disnake.Color(original_color))
        
        # 새 역할 부여 (1등만 first_role, 2-6등은 other_role)
        for index, (user_id, _) in enumerate(top_chatters):
            member = inter.guild.get_member(user_id)
            if member:
                if index == 0:  # 1등만
                    await member.add_roles(first_role)
                    role_type = "first"
                else:  # 2-6등
                    await member.add_roles(other_role)
                    role_type = "other"
                update_role_streak(guild_id, user_id, role_type)

        # 진행 상황 알림
        await inter.edit_original_response(content="이미지를 생성 중인 것이다... 🎨")

        # 이미지 생성
        image = await create_ranking_image(
            inter.guild,
            top_chatters,
            first_role,
            other_role,
            start_date=start_date_utc,
            end_date=end_date_utc
        )
        
        if image:
            # 채팅 카운트 초기화
            reset_chat_counts(guild_id)
            
            # 이미지 전송 및 마지막 집계 시간 저장
            await inter.edit_original_response(
                content=None,
                file=disnake.File(fp=image, filename="ranking.png")
            )
            
            # 현재 시간을 집계 날짜로 저장
            now_utc = datetime.datetime.now(pytz.UTC)
            save_last_aggregate_date(guild_id)
            
            # ===== 여기에 집계 기록 저장 코드 추가 =====
            try:
                # 집계 기록 저장
                db.save_aggregate_history(
                    guild_id=guild_id,
                    aggregate_date=now_utc,
                    start_date=start_date_utc,
                    end_date=end_date_utc,
                    top_chatters=top_chatters
                )
                print(f"[집계] 서버 {guild_id}의 집계 기록 저장 성공")
            except Exception as history_error:
                print(f"[집계] 집계 기록 저장 중 오류 발생: {history_error}")
                import traceback
                traceback.print_exc()
            
        else:
            await inter.edit_original_response(content="❌ 이미지 생성에 실패한 것이다...")

    except disnake.errors.InteractionResponded:
        # 이미 응답된 인터랙션에 대해 추가 응답 시도 시
        await inter.followup.send("❌ 이미 응답이 완료된 것이다. 다시 시도하는 것이다.", ephemeral=True)
    except disnake.errors.NotFound:
        # 인터랙션이 만료된 경우
        await inter.channel.send("❌ 처리 시간이 초과된 것이다. 다시 시도하는 것이다.")
    except Exception as e:
        print(f"Aggregate command error: {e}")
        try:
            await inter.followup.send("❌ 오류가 발생한 것이다. 다시 시도하는 것이다.", ephemeral=True)
        except:
            await inter.channel.send("❌ 오류가 발생한 것이다. 다시 시도하는 것이다.")

async def create_ranking_image(guild, top_chatters, first_role, other_role, start_date, end_date):
    width, height = 920, 1050
    
    # 기본 캔버스 생성
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    
    # 1. 배경 그라데이션 (파스텔 톤으로 변경)
    for y in range(height):
        progress = y / height
        r = int(155 + (190 - 155) * progress)  # 하늘색(155)에서 연보라(190)로
        g = int(190 + (170 - 190) * progress)  # 하늘색(190)에서 연보라(170)로
        b = int(255 + (245 - 255) * progress)  # 하늘색(255)에서 연보라(245)로
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 2. 사선 패턴 (선명하게 조정)
    pattern = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    pattern_draw = ImageDraw.Draw(pattern)
    
    line_spacing = 180
    line_width = 70
    footer = 50
    
    line_color = (255, 255, 255, 70)  # 투명도 유지
    
    for offset in range(-width, width * 2, line_spacing):
        start_x = offset + width
        start_y = 0
        end_x = offset
        end_y = height - footer
        
        for i in range(-line_width // 2, line_width // 2):
            pattern_draw.line(
                [(start_x + i, start_y), (end_x + i, end_y)],
                fill=line_color,
                width=1
            )
    
    # 배경에 사선 패턴 합성
    image.paste(pattern, (0, 0), pattern)

    # 3. 별 장식 추가
    def draw_sparkle(x, y, size):
        """반짝이는 별 장식을 그리는 함수"""
        sparkle = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        sparkle_draw = ImageDraw.Draw(sparkle)
        sparkle_draw.regular_polygon(
            (size // 2, size // 2, size // 3),
            n_sides=4,
            rotation=45,
            fill=(255, 255, 255, 100)
        )
        image.paste(sparkle, (x - size // 2, y - size // 2), sparkle)

    # 배경에 별 장식 배치
    for _ in range(15):
        x = random.randint(0, width)
        y = random.randint(0, height)
        size = random.randint(20, 40)
        draw_sparkle(x, y, size)

    # 4. 배경에 하트, 다이아몬드, 별, 원 장식 추가
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:  # RGB 형식
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (255,)  # A=255 추가
        elif len(hex_color) == 8:  # RGBA 형식
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4, 6))  # 그대로 반환
        else:
            raise ValueError("Invalid hex color format")

    # 순위별 색상 목록
    rank_colors = {
        "1등": "#DCD4FF",  # 더 차분한 라벤더
        "2등": "#D4E8FF",  # 더 차분한 베이비 블루
        "3등": "#D4FFEC",  # 더 차분한 소프트 민트
        "4등": "#FFECD4",  # 더 차분한 소프트 피치
        "5등": "#ECD4FF",  # 더 차분한 소프트 퍼플
        "6등": "#FFF8D4",  # 더 차분한 소프트 크림
        "count": "#666666",
        "name": "#FFFFFF",
        "role": "#4A4A4A"
    }

    # 장식 폰트 설정
    deco_font = ImageFont.truetype(MAIN_FONT_PATH, 20)

    # 장식 위치 분포 수정
    def draw_decorations_evenly(shape, count_range, color_opacity=50):  # 기존 70에서 50으로 낮춤
        """장식을 화면 전체에 고르게 분포"""
        count = random.randint(*count_range)
        sections = [
            (0, height // 3),
            (height // 3, 2 * height // 3),
            (2 * height // 3, height - footer)
        ]
        
        per_section = count // 3
        for section_start, section_end in sections:
            for _ in range(per_section):
                x = random.randint(0, width)
                # 오른쪽 영역은 피하도록 조정
                if x > width * 0.7:  # 오른쪽 30% 영역에는 더 적은 확률로 배치
                    if random.random() > 0.3:  # 70% 확률로 건너뛰기
                        continue
                y = random.randint(section_start, section_end)
                rank_key = random.choice([f"{i}등" for i in range(1, 7)])
                color = hex_to_rgb(rank_colors[rank_key])
                color = color[:3] + (color_opacity,)
                draw.text((x, y), shape, font=deco_font, fill=color, anchor="mm")

    # 장식 개수 조정 (하트 제거)
    # draw_decorations_evenly("♡", (5, 7))  # 하트 제거
    draw_decorations_evenly("◆", (4, 6))      # 다이아몬드
    draw_decorations_evenly("★", (5, 7))      # 별
    draw_decorations_evenly("●", (3, 5))      # 원

    # 5. 상단 흰색 도형 추가 (공백 제거용)
    white_height = 100
    white_rect = Image.new('RGBA', (width, white_height), (255, 255, 255, 255))
    image.paste(white_rect, (0, 0), white_rect)

    # 6. whole.png 불러오기 및 배치 (헤더와 로고를 하나로 합친 이미지)
    whole_path = WHOLE_IMAGE_PATH
    try:
        whole_image = Image.open(whole_path).convert("RGBA")
        whole_image = whole_image.resize((width, whole_image.height), Image.Resampling.LANCZOS)
        whole_y_offset = 0  # 상단에 배치
        image.paste(whole_image, (0, whole_y_offset), whole_image)
    except Exception as e:
        print(f"whole.png 로딩 실패: {e}")

    # 7. 왼쪽 모서리 색칠 장식 추가 (노란 네모 대신 골드 별)
    draw.text((10, white_height + 10), "★", font=deco_font, fill=(255, 215, 0, 255), anchor="mm")  # 골드 색상

    # 헤더 주변 골드 별 추가 (여러 위치에 배치)
    stars = [
        (10, white_height + 10, 255),       # 왼쪽 (기존)
        (35, white_height + 15, 200),       # 왼쪽 근처
        (width - 40, white_height + 12, 230), # 오른쪽
        (width - 70, white_height + 20, 180), # 오른쪽 근처
    ]
    
    for x, y, alpha in stars:
        draw.text((x, y), "★", font=deco_font, fill=(255, 215, 0, alpha), anchor="mm")

    # 폰트 설정
    font_title = ImageFont.truetype(MAIN_FONT_PATH, 72)
    font_bold = ImageFont.truetype(MAIN_FONT_PATH, 34)
    font_medium = ImageFont.truetype(MAIN_FONT_PATH, 26)
    font_regular = ImageFont.truetype(MAIN_FONT_PATH, 24)
    font_thin = ImageFont.truetype(MAIN_FONT_PATH, 20)
    font_small = ImageFont.truetype(MAIN_FONT_PATH, 22)
    font_small_gray = ImageFont.truetype(MAIN_FONT_PATH, 20)

    # 일본어/한자용 폰트 설정
    font_fallback_bold = ImageFont.truetype(FALLBACK_FONT_PATH, 34)
    font_fallback_medium = ImageFont.truetype(FALLBACK_FONT_PATH, 26)
    font_fallback_regular = ImageFont.truetype(FALLBACK_FONT_PATH, 24)
    font_fallback_small = ImageFont.truetype(FALLBACK_FONT_PATH, 22)

    # 폰트 경로를 상대 경로로 변경
    try:
        # 경로 확인
        import os
        
        # 폰트 파일 경로 (이미 정의된 경로 활용)
        print(f"폰트 디렉토리 경로: {FONT_DIR}")
        print(f"이미지 디렉토리 경로: {IMAGE_DIR}")
        print(f"현재 작업 디렉토리: {os.getcwd()}")
        
        # 파일 존재 여부 확인
        if not os.path.exists(MAIN_FONT_PATH):
            print(f"⚠️ 폰트 파일이 없습니다: {MAIN_FONT_PATH}")
        if not os.path.exists(FALLBACK_FONT_PATH):
            print(f"⚠️ 보조 폰트 파일이 없습니다: {FALLBACK_FONT_PATH}")
        if not os.path.exists(WHOLE_IMAGE_PATH):
            print(f"⚠️ 헤더 이미지 파일이 없습니다: {WHOLE_IMAGE_PATH}")
        
        # 폰트 설정 - 상대 경로 사용
        font_title = ImageFont.truetype(MAIN_FONT_PATH, 72)
        font_bold = ImageFont.truetype(MAIN_FONT_PATH, 34)
        font_medium = ImageFont.truetype(MAIN_FONT_PATH, 26)
        font_regular = ImageFont.truetype(MAIN_FONT_PATH, 24)
        font_thin = ImageFont.truetype(MAIN_FONT_PATH, 20)
        font_small = ImageFont.truetype(MAIN_FONT_PATH, 22)
        font_small_gray = ImageFont.truetype(MAIN_FONT_PATH, 20)

        # 일본어/한자용 폰트 설정
        font_fallback_bold = ImageFont.truetype(FALLBACK_FONT_PATH, 34)
        font_fallback_medium = ImageFont.truetype(FALLBACK_FONT_PATH, 26)
        font_fallback_regular = ImageFont.truetype(FALLBACK_FONT_PATH, 24)
        font_fallback_small = ImageFont.truetype(FALLBACK_FONT_PATH, 22)
        
        # whole.png 불러오기 및 배치
        whole_image = Image.open(WHOLE_IMAGE_PATH).convert("RGBA")
        whole_image = whole_image.resize((width, whole_image.height), Image.Resampling.LANCZOS)
        whole_y_offset = 0  # 상단에 배치
        image.paste(whole_image, (0, whole_y_offset), whole_image)
        
    except Exception as e:
        print(f"폰트 또는 이미지 로딩 오류: {e}")
        import traceback
        traceback.print_exc()
        return None

    def get_font(text, default_font, fallback_font):
        """일본어/한자 텍스트를 위한 폰트 선택"""
        if any(('\u3040' <= char <= '\u309f') or  # 히라가나
               ('\u30a0' <= char <= '\u30ff') or  # 가타카나
               ('\u4e00' <= char <= '\u9faf') or  # 한자
               ('\u3400' <= char <= '\u4dbf') for char in text):  # 확장 한자
            if default_font.size >= 34:
                return font_fallback_bold
            elif default_font.size >= 26:
                return font_fallback_medium
            elif default_font.size >= 24:
                return font_fallback_regular
            else:
                return font_fallback_small
        return default_font

    def get_fitting_font_size(text, max_width, base_font_path, start_size, min_size=16):
        """텍스트가 주어진 너비에 맞도록 폰트 크기를 조절하는 함수"""
        current_size = start_size
        while current_size >= min_size:
            test_font = ImageFont.truetype(base_font_path, current_size)
            text_width = draw.textlength(text, font=test_font)
            if text_width <= max_width:
                return current_size
            current_size -= 1
        return min_size

    # 섹션 배경 디자인 (순위별 하트와 대각선 줄무늬 추가)
    def draw_rank_background(x, y, bw, bh, rank_index=None):
        """순위 섹션 배경을 그리는 함수"""
        x = int(x)
        y = int(y)
        bw = int(bw)
        bh = int(bh)

        # 그림자 효과
        for i in range(4):
            shadow = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_radius = 20
            shadow_alpha = 10 - (i * 2)
            shadow_color = (0, 0, 0, shadow_alpha)
            
            shadow_draw.rounded_rectangle(
                [(i, i), (bw-1+i, bh-1+i)],
                shadow_radius,
                fill=shadow_color
            )
            image.paste(shadow, (x, y), shadow)

        # 메인 섹션 배경
        mask = Image.new('L', (bw, bh), 0)
        mask_draw = ImageDraw.Draw(mask)
        radius = 20
        mask_draw.rounded_rectangle([(0, 0), (bw-1, bh-1)], radius, fill=255)
        
        gradient = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
        gradient_draw = ImageDraw.Draw(gradient)
        
        gradient_top = (225, 230, 245, 255)     # 연한 파스텔 블루
        gradient_bottom = (220, 225, 240, 255)  # 비슷한 톤의 연한 라벤더
        
        for i in range(bh):
            progress = i / bh
            r = int(gradient_top[0] + (gradient_bottom[0] - gradient_top[0]) * progress)
            g = int(gradient_top[1] + (gradient_bottom[1] - gradient_top[1]) * progress)
            b = int(gradient_top[2] + (gradient_bottom[2] - gradient_top[2]) * progress)
            a = int(gradient_top[3] + (gradient_bottom[3] - gradient_top[3]) * progress)
            gradient_draw.line([(0, i), (bw-1, i)], fill=(r, g, b, a))
        
        gradient.putalpha(mask)
        image.paste(gradient, (x, y), gradient)
        
        # 순위별 하트 패턴 추가 (수정된 부분)
        heart_pattern = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
        heart_draw = ImageDraw.Draw(heart_pattern)
        if rank_index is not None:
            heart_color = hex_to_rgb(rank_colors[f"{rank_index + 1}등"])
            heart_color = (*heart_color[:3], 50)  # RGB만 사용, A=50
        else:
            heart_color = (255, 255, 255, 50)
        for i in range(3):
            for j in range(3):
                heart_x = 40 + i * (bw // 4)
                heart_y = 40 + j * (bh // 4)
                # 왼쪽 상단 코너(0,0)에는 하트를 그리지 않음
                if not (i == 0 and j == 0):
                    heart_draw.text((heart_x, heart_y), "♡", font=font_small, fill=heart_color, anchor="mm")
        image.paste(heart_pattern, (x, y), heart_pattern)
        
        
        
        # 이중 테두리
        inner_border_color = (255, 255, 255, 200)
        inner_border_width = 5
        outer_border_width = 3
        
        draw.rounded_rectangle(
            [(x, y), (x+bw-1, y+bh-1)],
            radius,
            outline=inner_border_color,
            width=inner_border_width
        )
        
        if rank_index is not None:
            outer_border_color = hex_to_rgb(rank_colors[f"{rank_index + 1}등"])
            draw.rounded_rectangle(
                [(x - outer_border_width, y - outer_border_width), (x + bw - 1 + outer_border_width, y + bh - 1 + outer_border_width)],
                radius + outer_border_width,
                outline=outer_border_color,
                width=outer_border_width
            )

        # 왼쪽 상단 삼각형 장식
        corner_size = 30
        if rank_index is not None:
            corner_color = hex_to_rgb(rank_colors[f"{rank_index + 1}등"])
        else:
            corner_color = (255, 255, 153, 255)
        draw.polygon([(x, y), (x + corner_size, y), (x, y + corner_size)], fill=corner_color)

    # 섹션 위치 설정
    x_center_offset = 70
    x_offset_left = (width // 4 - 50) - x_center_offset
    x_offset_right = x_offset_left + 290 + 50
    
    margin_top = 40
    y_offset_top = margin_top + 240
    y_offset_bottom = y_offset_top + 340

    section_width = 290
    section_height = 300
    small_section_width = 400
    small_section_height = 140

    second_section_end = y_offset_bottom + section_height - 15
    total_height_3_to_6 = second_section_end - (y_offset_top - 15)
    y_spacing = int((total_height_3_to_6 - (small_section_height * 4)) / 3)

    # 배경 그리기
    draw_rank_background(x_offset_left - 15, y_offset_top - 15, section_width, section_height, rank_index=0)
    draw_rank_background(x_offset_left - 15, y_offset_bottom - 15, section_width, section_height, rank_index=1)

    for i in range(2, 6):
        y_pos = int((y_offset_top - 15) + (i - 2) * (small_section_height + y_spacing) + 5)
        draw_rank_background(x_offset_right - 15, y_pos, small_section_width, small_section_height, rank_index=i)

    # 별 장식 추가
    draw_sparkle(x_offset_left, y_offset_top, 30)
    draw_sparkle(x_offset_left + section_width - 30, y_offset_top, 20)
    draw_sparkle(x_offset_left, y_offset_bottom, 25)
    draw_sparkle(x_offset_right, y_offset_top, 30)
    draw_sparkle(x_offset_right + small_section_width - 30, y_offset_top, 20)

    # 프로필 이미지 처리
    async def get_high_quality_avatar(member, size, rank_index=None):
        try:
            avatar = await member.avatar.read()
            avatar_image = Image.open(io.BytesIO(avatar)).convert('RGBA')
            
            border_width = size // 25 if rank_index is not None and rank_index >= 2 else size // 35
            corner_radius = size // 5
            final_size = size + (border_width * 2)

            def get_rank_border_color(index):
                if index == 0:
                    return (220, 212, 255, 255)
                elif index == 1:
                    return (212, 232, 255, 255)
                else:
                    return (228, 228, 255, 255)

            final_image = Image.new('RGBA', (final_size, final_size), (0, 0, 0, 0))
            border_mask = Image.new('L', (final_size, final_size), 0)
            border_draw = ImageDraw.Draw(border_mask)
            border_radius = corner_radius + border_width // 2
            border_draw.rounded_rectangle([(0, 0), (final_size-1, final_size-1)],
                                          border_radius,
                                          fill=255)

            border_color = get_rank_border_color(rank_index) if rank_index is not None else (228, 228, 255, 255)
            border = Image.new('RGBA', (final_size, final_size), border_color)
            border.putalpha(border_mask)
            final_image.paste(border, (0, 0), border_mask)

            inner_mask = Image.new('L', (size, size), 0)
            inner_draw = ImageDraw.Draw(inner_mask)
            inner_radius = corner_radius - border_width // 2
            inner_draw.rounded_rectangle([(0, 0), (size-1, size-1)],
                                         inner_radius,
                                         fill=255)

            avatar_image = avatar_image.resize((size, size), Image.Resampling.LANCZOS)
            masked_avatar = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            masked_avatar.paste(avatar_image, (0, 0))
            masked_avatar.putalpha(inner_mask)

            final_image.paste(masked_avatar, (border_width, border_width), masked_avatar)
            return final_image

        except Exception as e:
            print(f"Avatar processing error: {e}")
            return Image.new('RGBA', (size, size), (65, 70, 95, 255))

    # 텍스트 렌더링 (테두리 두께 줄임)
    def draw_text_with_outline(x, y, text, font, main_color, outline_color=None, outline_width=3, is_name=False):
        if outline_color is None:
            if is_name:
                outline_color = (80, 90, 150)
                outline_width = 2  # 4에서 2로 변경
            else:
                if text.endswith("등"):
                    rank = text.rstrip("등")
                    if rank == "1":
                        outline_color = (150, 140, 200)
                    elif rank == "2":
                        outline_color = (140, 160, 200)
                    elif rank == "3":
                        outline_color = (140, 200, 180)
                    elif rank == "4":
                        outline_color = (200, 160, 140)
                    elif rank == "5":
                        outline_color = (160, 140, 200)
                    elif rank == "6":
                        outline_color = (200, 180, 140)
                    outline_width = 3
                else:
                    outline_color = (80, 90, 150)
                    outline_width = 3

        directions = [
            (-outline_width, 0), (outline_width, 0),
            (0, -outline_width), (0, outline_width),
            (-outline_width, -outline_width),
            (-outline_width, outline_width),
            (outline_width, -outline_width),
            (outline_width, outline_width),
            (-outline_width//2, -outline_width),
            (-outline_width//2, outline_width),
            (outline_width//2, -outline_width),
            (outline_width//2, outline_width),
        ]
        
        for thickness in range(1, outline_width + 1):
            for dx, dy in directions:
                draw.text((x + dx/thickness, y + dy/thickness),
                          text, font=font,
                          fill=outline_color,
                          anchor="lt")
        
        draw.text((x, y), text, font=font, fill=main_color, anchor="lt")

    def draw_role_name_with_streak(x, y, role_name, streak_count, font, role_color):
        draw.text((x, y), role_name, font=font, fill=role_color, anchor="lt")
        if streak_count > 1:
            streak_x = x + draw.textlength(role_name, font=font) + 5
            streak_text = f" ({streak_count}회 연속)"
            streak_color = rank_colors["count"]
            smaller_font = ImageFont.truetype(font.path, font.size - 2)
            draw.text((streak_x, y + 1), streak_text,
                      font=smaller_font,
                      fill=streak_color,
                      anchor="lt")

    # 순위별 장식
    def draw_rank_decoration(x, y, rank_index):
        deco_font = ImageFont.truetype(MAIN_FONT_PATH, 24)
        if rank_index == 0:
            draw.regular_polygon((x, y, 15), n_sides=4, rotation=45, fill=(255, 215, 0, 255))
        elif rank_index == 1:
            draw.text((x, y), "♡", font=font_medium, fill=(255, 182, 193, 255), anchor="mm")
        elif rank_index == 2:
            color = hex_to_rgb(rank_colors["3등"])
            color = color[:3] + (200,)
            draw.text((x, y), "♡", font=deco_font, fill=color, anchor="mm")
        elif rank_index == 3:
            color = hex_to_rgb(rank_colors["4등"])
            color = color[:3] + (200,)
            draw.text((x, y), "★", font=deco_font, fill=color, anchor="mm")
        elif rank_index == 4:
            color = hex_to_rgb(rank_colors["5등"])
            color = color[:3] + (200,)
            draw.text((x, y), "◆", font=deco_font, fill=color, anchor="mm")
        elif rank_index == 5:
            color = hex_to_rgb(rank_colors["6등"])
            color = color[:3] + (200,)
            draw.text((x, y), "★", font=deco_font, fill=color, anchor="mm")

    # 순위 처리
    try:
        if len(top_chatters) > 0:
            user_id, count = top_chatters[0]
            member = guild.get_member(user_id)
            if member:
                avatar_image = await get_high_quality_avatar(member, 150, rank_index=0)
                border_offset = avatar_image.size[0] - 150
                image.paste(avatar_image,
                            (x_offset_left, y_offset_top + 6),
                            avatar_image)

                text_x = x_offset_left
                draw_text_with_outline(text_x, y_offset_top + 180, "1등",
                                       font=font_medium,
                                       main_color=rank_colors["1등"])
                draw.text((text_x + draw.textlength("1등", font=font_medium) + 8, y_offset_top + 182),
                          f"({count}회)", font=font_small_gray, fill=rank_colors["count"], anchor="lt")
                
                # 이름 폰트 크기 조절 (1등)
                name_max_width = section_width - 20  # 여백 고려
                name_font_size = get_fitting_font_size(
                    member.display_name,
                    name_max_width,
                    MAIN_FONT_PATH,
                    34  # 기존 크기
                )
                adjusted_font = ImageFont.truetype(MAIN_FONT_PATH, name_font_size)
                
                # 폰트 크기에 따라 y 위치 미세 조정
                y_offset = (34 - name_font_size) / 2  # 기존 크기와의 차이를 보정
                draw_text_with_outline(text_x, y_offset_top + 215 + y_offset, member.display_name,
                                     font=get_font(member.display_name, adjusted_font, font_fallback_bold),
                                     main_color=rank_colors["name"],
                                     is_name=True)
                
                streak_info = get_role_streak(guild.id, user_id)
                role_color = f"#{first_role.color.value:06x}"
                draw_role_name_with_streak(text_x, y_offset_top + 250,
                                           first_role.name,
                                           streak_info['count'],
                                           font_small,
                                           role_color)
                draw_rank_decoration(x_offset_left + section_width - 30, y_offset_top + 30, 0)

        if len(top_chatters) > 1:
            user_id, count = top_chatters[1]
            member = guild.get_member(user_id)
            if member:
                avatar_image = await get_high_quality_avatar(member, 150, rank_index=1)
                border_offset = avatar_image.size[0] - 150
                image.paste(avatar_image,
                            (x_offset_left, y_offset_bottom + 15),
                            avatar_image)

                text_x = x_offset_left
                draw_text_with_outline(text_x, y_offset_bottom + 180, "2등",
                                       font=font_medium,
                                       main_color=rank_colors["2등"])
                draw.text((text_x + draw.textlength("2등", font=font_medium) + 10, y_offset_bottom + 182),
                          f"({count}회)", font=font_small_gray, fill=rank_colors["count"], anchor="lt")
                
                # 이름 폰트 크기 조절 (2등)
                name_max_width = section_width - 20
                name_font_size = get_fitting_font_size(
                    member.display_name,
                    name_max_width,
                    MAIN_FONT_PATH,
                    34
                )
                adjusted_font = ImageFont.truetype(MAIN_FONT_PATH, name_font_size)
                
                y_offset = (34 - name_font_size) / 2
                draw_text_with_outline(text_x, y_offset_bottom + 210 + y_offset, member.display_name,
                                     font=get_font(member.display_name, adjusted_font, font_fallback_bold),
                                     main_color=rank_colors["name"],
                                     is_name=True)
                
                streak_info = get_role_streak(guild.id, user_id)
                role_color = f"#{other_role.color.value:06x}"
                draw_role_name_with_streak(text_x, y_offset_bottom + 250,
                                           other_role.name,
                                           streak_info['count'],
                                           font_small,
                                           role_color)
                draw_rank_decoration(x_offset_left + section_width - 30, y_offset_bottom + 30, 1)

        for index in range(2, len(top_chatters)):
            user_id, count = top_chatters[index]
            member = guild.get_member(user_id)
            if member:
                y_pos = int((y_offset_top - 15) + (index - 2) * (small_section_height + y_spacing) + 5 + 15)
                
                avatar_image = await get_high_quality_avatar(member, 90, rank_index=index)
                border_offset = avatar_image.size[0] - 90
                image.paste(avatar_image,
                            (x_offset_right - border_offset//2 + 10,
                             y_pos - border_offset//2 + 10),
                            avatar_image)

                x_text = x_offset_right + 130
                draw_text_with_outline(x_text, y_pos + 17, f"{index + 1}등",
                                       font=font_medium,
                                       main_color=rank_colors[f"{index + 1}등"])
                draw.text((x_text + draw.textlength(f"{index + 1}등", font=font_medium) + 10, y_pos + 17),
                          f"({count}회)", font=font_small_gray, fill=rank_colors["count"], anchor="lt")
                
                # 이름 폰트 크기 조절 (3-6등)
                name_max_width = small_section_width - 160  # 아바타와 여백 고려
                name_font_size = get_fitting_font_size(
                    member.display_name,
                    name_max_width,
                    MAIN_FONT_PATH,
                    26  # 3-6등의 기본 폰트 크기
                )
                adjusted_font = ImageFont.truetype(MAIN_FONT_PATH, name_font_size)
                
                y_offset = (26 - name_font_size) / 2
                draw_text_with_outline(x_text, y_pos + 47 + y_offset, member.display_name,
                                     font=get_font(member.display_name, adjusted_font, font_fallback_medium),
                                     main_color=rank_colors["name"],
                                     is_name=True)
                
                streak_info = get_role_streak(guild.id, user_id)
                role_color = f"#{other_role.color.value:06x}"
                draw_role_name_with_streak(x_text, y_pos + 77,
                                           other_role.name,
                                           streak_info['count'],
                                           font_small,
                                           role_color)
                draw_rank_decoration(x_offset_right + small_section_width - 30, y_pos + 20, index)

    except Exception as e:
        print(f"이미지 생성 중 오류 발생: {e}")
        import traceback
        print(traceback.format_exc())
        return None

    # 집계 시간과 기간 표시 (수정된 부분)
    now_utc = datetime.datetime.now(pytz.utc)
    now_kst = now_utc.astimezone(pytz.timezone('Asia/Seoul'))
    start_kst = start_date.astimezone(pytz.timezone('Asia/Seoul'))
    end_kst = end_date.astimezone(pytz.timezone('Asia/Seoul'))
    
    days_diff = (end_kst.date() - start_kst.date()).days + 1
    start_str = start_kst.strftime("%y/%m/%d")
    end_str = end_kst.strftime("%y/%m/%d")
    
    hour_str = "오전" if now_kst.hour < 12 else "오후"
    hour_12 = now_kst.hour if now_kst.hour <= 12 else now_kst.hour - 12
    if hour_12 == 0:
        hour_12 = 12
    time_str = f"{now_kst.strftime('%Y/%m/%d')} {hour_str} {hour_12}시 {now_kst.strftime('%M분 %S초')}"
    
    period_str = f"집계 기간: {start_str} ~ {end_str} ({days_diff}일)"
    time_color = (220, 220, 220)  # 연한 흰색으로 변경
    
    # 테두리 없이 심플하게 텍스트만 표시
    draw.text((width // 2, height - 25), f"{time_str} | {period_str}",
              font=font_thin, fill=time_color, anchor="mm")

    # 서버 정보 표시
    try:
        avatar_size = 35
        avatar = await guild.icon.read()
        avatar_image = Image.open(io.BytesIO(avatar)).convert('RGBA')
        avatar_image = avatar_image.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

        avatar_x = 30
        avatar_y = margin_top + 20
        image.paste(avatar_image, (avatar_x, avatar_y), avatar_image)
        
        server_name_color = (50, 50, 100)  # 진한 네이비 블루
        name_x = avatar_x + avatar_size + 10
        base_y = avatar_y  # 프로필 사진 y좌표와 동일하게 시작
        
        # 서버 이름 줄바꿈 처리 개선
        guild_name = guild.name
        max_width = 200  # 최대 너비 (픽셀)
        font = get_font(guild_name, font_regular, font_fallback_regular)
        
        # 문자 단위로 줄바꿈 처리
        chars = list(guild_name)
        lines = []
        current_line = []
        current_width = 0
        
        for char in chars:
            char_width = draw.textlength(char, font=font)
            
            if current_width + char_width <= max_width:
                current_line.append(char)
                current_width += char_width
            else:
                if current_line:
                    current_text = ''.join(current_line)
                    # 현재 줄이 여전히 너무 길다면 다시 분할
                    if draw.textlength(current_text, font=font) > max_width:
                        mid = len(current_text) // 2
                        lines.append(current_text[:mid])
                        current_line = list(current_text[mid:] + char)
                    else:
                        lines.append(current_text)
                        current_line = [char]
                    current_width = char_width

        if current_line:
            current_text = ''.join(current_line)
            if draw.textlength(current_text, font=font) > max_width:
                mid = len(current_text) // 2
                lines.append(current_text[:mid])
                lines.append(current_text[mid:])
            else:
                lines.append(current_text)
        
        # 줄바꿈된 텍스트 그리기
        line_height = font.size + 2
        total_height = line_height * len(lines)
        # 첫 번째 줄이 프로필 사진 중앙에 오도록 조정
        start_y = base_y + (avatar_size - total_height) // 2
        
        for i, line in enumerate(lines):
            line_y = start_y + i * line_height
            
            # 테두리와 텍스트 그리기
            outline_color = (255, 255, 255, 200)
            outline_width = 2
            
            # 테두리
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((name_x + dx, line_y + dy),
                                line,
                                font=font,
                                fill=outline_color,
                                anchor="lt")
            
            # 메인 텍스트
            draw.text((name_x, line_y),
                      line,
                      font=font,
                      fill=server_name_color,
                      anchor="lt")

    except Exception as e:
        print(f"서버 프로필 사진 로딩 실패: {e}")

    # 이미지 저장 및 반환
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG", optimize=False, quality=100)
    image_bytes.seek(0)
    return image_bytes