import disnake
from disnake.ext import commands
from bot import bot, server_roles, conn, c
import re

# 원래 역할 색상 저장을 위한 테이블 생성
def setup_role_colors_table():
    c.execute('''CREATE TABLE IF NOT EXISTS role_original_colors (
                    guild_id INTEGER,
                    role_id INTEGER,
                    original_color INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )''')
    conn.commit()
    print("Role colors table initialized")

# 테이블 초기화
setup_role_colors_table()

# 원래 역할 색상 저장 함수
def save_original_role_color(guild_id, role_id, color):
    c.execute("""
        INSERT OR IGNORE INTO role_original_colors
        (guild_id, role_id, original_color)
        VALUES (?, ?, ?)
    """, (guild_id, role_id, color))
    conn.commit()

# 원래 역할 색상 가져오기 함수
def get_original_role_color(guild_id, role_id):
    c.execute("""
        SELECT original_color FROM role_original_colors
        WHERE guild_id = ? AND role_id = ?
    """, (guild_id, role_id))
    row = c.fetchone()
    return row[0] if row else None

@bot.slash_command(
    name="역할색상",
    description="1등 역할의 색상을 변경하는 것이다. (관리자 또는 1등 역할 보유자만 사용 가능한 것이다)"
)
async def role_color(
    inter: disnake.ApplicationCommandInteraction,
    색상: str = commands.Param(description="HEX 색상 코드 (예: #FF5733)")
):
    guild_id = inter.guild.id
    
    # 서버에 설정된 역할 확인
    if guild_id not in server_roles:
        await inter.response.send_message("❌ 역할이 설정되지 않은 것이다. /역할설정 명령어를 먼저 사용하는 것이다.", ephemeral=True)
        return
    
    # 1등 역할 가져오기
    first_role_id = server_roles[guild_id].get("first")
    if not first_role_id:
        await inter.response.send_message("❌ 1등 역할이 설정되지 않은 것이다.", ephemeral=True)
        return
    
    first_role = inter.guild.get_role(first_role_id)
    if not first_role:
        await inter.response.send_message("❌ 설정된 1등 역할을 찾을 수 없는 것이다.", ephemeral=True)
        return
    
    # 권한 확인 (관리자 또는 1등 역할 보유자)
    has_permission = inter.author.guild_permissions.administrator or first_role in inter.author.roles
    if not has_permission:
        await inter.response.send_message("❌ 이 명령어는 관리자 또는 1등 역할을 가진 사람만 사용할 수 있는 것이다.", ephemeral=True)
        return
    
    # 색상 코드 유효성 확인
    color_pattern = r'^#?(?:[0-9a-fA-F]{3}){1,2}$'
    if not re.match(color_pattern, 색상):
        await inter.response.send_message("❌ 유효한 HEX 색상 코드를 입력하는 것이다. (예: #FF5733)", ephemeral=True)
        return
    
    # # 제거 및 색상 변환
    if 색상.startswith('#'):
        색상 = 색상[1:]
    
    # 3자리 색상 코드를 6자리로 확장 (예: FFF -> FFFFFF)
    if len(색상) == 3:
        색상 = ''.join(c + c for c in 색상)
    
    # 색상 코드를 정수로 변환
    try:
        color_int = int(색상, 16)
    except ValueError:
        await inter.response.send_message("❌ 색상 코드 변환에 실패한 것이다.", ephemeral=True)
        return
    
    # 원래 색상 저장 (존재하지 않을 경우에만)
    save_original_role_color(guild_id, first_role_id, first_role.color.value)
    
    # 역할 색상 변경
    try:
        await first_role.edit(color=disnake.Color(color_int))
        await inter.response.send_message(f"✅ 1등 역할 '{first_role.name}'의 색상이 변경된 것이다.", ephemeral=True)
    except Exception as e:
        await inter.response.send_message(f"❌ 역할 색상 변경 중 오류가 발생한 것이다: {e}", ephemeral=True)

# 집계 명령어에서 역할 색상을 원래대로 복원하는 함수 (aggregate.py에서 호출)
def restore_role_original_color(guild, role):
    guild_id = guild.id
    role_id = role.id
    
    # 원래 색상 조회
    original_color = get_original_role_color(guild_id, role_id)
    if original_color:
        try:
            # 비동기 작업이지만 동기적으로 처리 (주의: 이상적이지 않음)
            # 필요시 aggregate.py에서 비동기적으로 처리하도록 수정 필요
            return original_color
        except Exception as e:
            print(f"역할 색상 복원 중 오류 발생: {e}")
            return None
