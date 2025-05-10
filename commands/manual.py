from disnake.ext import commands
import disnake
from bot import bot, server_roles, server_excluded_roles, server_chat_counts
import database as db
import os
import pytz
from datetime import datetime

@bot.slash_command(name="메뉴얼", description="미즈키 사용 설명서를 보여주는 것이다.")
async def 메뉴얼(inter: disnake.ApplicationCommandInteraction):
    # 기본 임베드 생성
    embed = disnake.Embed(
        title="미즈키 사용 설명서",
        description="서버의 채팅을 집계하여 역할을 부여하는 봇인 것이다!",
        color=disnake.Color.blue()
    )
    
    # 메뉴얼 내용 설정
    embed.add_field(
        name="🔍 기본 기능",
        value=(
            "이 봇은 서버 내 사용자들의 채팅을 집계하는 것이다!\n"
            "**`/집계`** 명령어를 통해 가장 많이 채팅한 6명에게 역할을 부여하는 것이다!\n"
            "1위 사용자는 특별한 역할을 받게 되는 것이다!\n"
            "연속으로 순위권에 들면 연속 집계 횟수도 표시되는 것이다!"
        ),
        inline=False
    )
    
    # 관리자 명령어 설명
    embed.add_field(
        name="⚙️ 관리자 명령어",
        value=(
            "`/역할설정` - 1위와 2~6위에게 부여할 역할을 설정하는 것이다!\n"
            "`/역할제외` - 집계에서 제외할 역할을 설정하는 것이다!\n"
            "`/집계` - 특정 기간의 채팅을 집계하여 역할을 부여하는 것이다!\n"
            "  → 형식: YYYYMMDD (예: 20230101) 또는 't'(오늘)\n"
            "`/역할색상` - 1위 역할의 색상을 변경하는 것이다!\n"
            "`/연속초기화` - 특정 사용자의 연속 집계 기록을 초기화하는 것이다!\n"
        ),
        inline=False
    )
    
    # 일반 명령어 설명
    embed.add_field(
        name="📋 일반 명령어",
        value=(
            "`/리더보드` - 채팅 순위를 보여주는 것이다!\n"
            "`/오미쿠지` - 오늘의 운세를 확인하는 것이다!\n"
            "`/tenor` - 테놀 GIF를 검색하는 것이다!\n"
            "`/메뉴얼` - 이 도움말을 보는 것이다!\n"
            "`/핑` - 봇의 응답 속도를 확인하는 것이다!"
        ),
        inline=False
    )
    
    # 집계 방식 설명
    embed.add_field(
        name="📊 집계 방식",
        value=(
            "1. 봇이 서버의 모든 채팅을 자동으로 집계하는 것이다!\n"
            "2. `/집계` 명령어로 특정 기간의 채팅량을 확인하는 것이다!\n"
            "3. 상위 6명의 사용자에게 역할이 부여되는 것이다!\n"
            "4. 1위는 특별한 역할을, 2~6위는 다른 역할을 받는 것이다!\n"
            "5. 역할은 `/역할설정` 명령어로 미리 지정해야 하는 것이다!\n"
            "6. 제외 역할을 가진 사용자는 집계에서 제외되는 것이다!"
        ),
        inline=False
    )
    
    # 푸터 추가
    embed.set_footer(text="더 궁금한 점이 있다면 관리자에게 문의하는 것이다!")
    
    # 버튼 뷰 생성
    class ManualView(disnake.ui.View):
        def __init__(self):
            super().__init__(timeout=300)  # 5분 타임아웃
            
        @disnake.ui.button(label="서버 정보", style=disnake.ButtonStyle.primary, emoji="🖥️")
        async def server_info(self, button: disnake.ui.Button, button_inter: disnake.MessageInteraction):
            # 관리자인지 확인
            if not button_inter.author.guild_permissions.administrator:
                await button_inter.response.send_message("이 기능은 관리자만 사용할 수 있는 것이다!", ephemeral=True)
                return
                
            # 서버 정보 임베드 생성
            guild_id = button_inter.guild.id
            guild = button_inter.guild
            
            info_embed = disnake.Embed(
                title=f"🖥️ {guild.name} 서버 정보",
                description="이 서버에 대해 내가 알고 있는 정보인 것이다!",
                color=disnake.Color.green()
            )
            
            # 역할 설정 정보
            role_info = "❌ 설정되지 않은 것이다! `/역할설정` 명령어로 설정하는 것이다!"
            if guild_id in server_roles:
                first_role_id = server_roles[guild_id].get('first')
                other_role_id = server_roles[guild_id].get('other')
                
                first_role = disnake.utils.get(guild.roles, id=first_role_id)
                other_role = disnake.utils.get(guild.roles, id=other_role_id)
                
                if first_role and other_role:
                    role_info = f"1위 역할: {first_role.mention} (ID: {first_role_id})\n" \
                               f"2~6위 역할: {other_role.mention} (ID: {other_role_id})"
            
            info_embed.add_field(name="🏆 역할 설정", value=role_info, inline=False)
            
            # 제외 역할 정보
            excluded_info = "❕ 설정된 제외 역할이 없는 것이다!"
            if guild_id in server_excluded_roles and server_excluded_roles[guild_id]:
                excluded_roles = []
                for role_id in server_excluded_roles[guild_id]:
                    role = disnake.utils.get(guild.roles, id=role_id)
                    if role:
                        excluded_roles.append(f"• {role.mention} (ID: {role_id})")
                
                if excluded_roles:
                    excluded_info = "\n".join(excluded_roles)
            
            info_embed.add_field(name="🚫 제외 역할", value=excluded_info, inline=False)
            
            # 마지막 집계 날짜 정보
            last_aggregate = "❕ 아직 집계를 한 적이 없는 것이다!"
            if db.is_mongo_connected():
                try:
                    last_date = db.get_last_aggregate_date(guild_id)
                    if last_date:
                        kst = pytz.timezone('Asia/Seoul')
                        last_date_kst = last_date.astimezone(kst)
                        last_aggregate = last_date_kst.strftime("%Y년 %m월 %d일 %H시 %M분")
                except Exception as e:
                    last_aggregate = f"❌ 집계 날짜를 확인하는 중 오류가 발생한 것이다: {e}"
            
            info_embed.add_field(name="📅 마지막 집계 일시", value=last_aggregate, inline=False)
            
            # 서버 통계 정보
            total_members = len(guild.members)
            bot_count = sum(1 for member in guild.members if member.bot)
            human_count = total_members - bot_count
            
            stats = f"👥 총 멤버: {total_members}명\n" \
                   f"👤 사용자: {human_count}명\n" \
                   f"🤖 봇: {bot_count}개"
            
            info_embed.add_field(name="📊 서버 통계", value=stats, inline=False)
            
            # 리더보드 정보
            leaderboard_info = "❌ 채팅 데이터가 없는 것이다!"
            if guild_id in server_chat_counts and server_chat_counts[guild_id]:
                chat_counts = server_chat_counts[guild_id]
                
                if not chat_counts:
                    # DB에서 직접 로드 시도
                    try:
                        db_counts = db.get_guild_chat_counts(guild_id)
                        if db_counts:
                            from collections import Counter
                            chat_counts = Counter(db_counts)
                            server_chat_counts[guild_id] = chat_counts
                    except Exception as e:
                        leaderboard_info = f"❌ 채팅 데이터 로드 중 오류: {e}"
                
                if chat_counts:
                    sorted_users = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    
                    if sorted_users:
                        leaderboard_lines = []
                        for i, (user_id, count) in enumerate(sorted_users, 1):
                            member = guild.get_member(user_id)
                            name = member.display_name if member else f"알 수 없는 사용자 ({user_id})"
                            leaderboard_lines.append(f"**{i}등**: {name} - {count}회")
                        
                        leaderboard_info = "\n".join(leaderboard_lines)
            
            info_embed.add_field(name="🏆 현재 리더보드 (상위 5명)", value=leaderboard_info, inline=False)
            
            # 현재 시간 표시
            kst_now = datetime.now(pytz.timezone('Asia/Seoul'))
            formatted_now = kst_now.strftime("%Y-%m-%d %H:%M:%S")
            info_embed.set_footer(text=f"정보 조회 시간: {formatted_now}")
            
            await button_inter.response.send_message(embed=info_embed, ephemeral=True)
    
    # 뷰와 함께 메뉴얼 전송
    await inter.response.send_message(embed=embed, view=ManualView())