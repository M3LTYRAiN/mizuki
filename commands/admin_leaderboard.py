from disnake.ext import commands
import disnake
from disnake.ui import Button, View
from bot import bot, server_chat_counts, server_excluded_roles
import database as db
import pytz
from collections import Counter

class AdminLeaderboardView(View):
    def __init__(self, author_id, guild_id, current_page=1):
        super().__init__()
        self.guild_id = guild_id
        self.current_page = current_page
        self.author_id = author_id
        self.chat_counts = server_chat_counts[self.guild_id]
        
        # 모든 사용자 포함하여 초기 정렬
        sorted_chatters = sorted(self.chat_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 페이지당 사용자 수
        self.items_per_page = 25
        
        # 제외된 역할을 가진 사용자 필터링 (바로 필터링하지는 않고, update_page에서 수행)
        self.max_page = 1  # 초기값, update_page에서 갱신됨
        
        # 명령어 사용자의 순위 찾기
        self.user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_chatters) if uid == author_id), None)
        if self.user_rank:
            self.user_page = (self.user_rank - 1) // self.items_per_page + 1
        else:
            self.user_page = None

    async def update_page(self, inter):
        # 모든 사용자 포함한 전체 채팅 데이터
        chat_counts = self.chat_counts
        all_chatters = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 제외된 역할 정보 가져오기
        excluded_roles = server_excluded_roles.get(self.guild_id, [])
        
        # 제외된 역할을 가진 사용자만 필터링
        excluded_members = []
        for user_id, count in all_chatters:
            member = inter.guild.get_member(user_id)
            if member and any(role.id in excluded_roles for role in member.roles):
                excluded_members.append((user_id, count))
        
        # 총 제외된 사용자 수
        total_excluded = len(excluded_members)
        
        # 페이지네이션 계산
        self.max_page = max(1, (total_excluded + self.items_per_page - 1) // self.items_per_page)
        self.current_page = max(1, min(self.current_page, self.max_page))
        
        # 현재 페이지에 표시할 데이터
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = min(start_index + self.items_per_page, total_excluded)
        page_data = excluded_members[start_index:end_index]
        
        # 임베드 생성 - 색상을 빨간색으로 변경
        embed = disnake.Embed(
            title="관리자용 리더보드 (제외된 역할만)",
            description=f"총 {total_excluded}명의 제외된 역할 사용자",
            color=disnake.Color.red()  # 색상을 빨간색으로 설정
        )

        # 현재 사용자 정보
        command_user = inter.author
        user_count = chat_counts.get(command_user.id, 0)
        
        # 제외된 사용자 목록 표시
        leaderboard_text = ""
        if page_data:
            for index, (user_id, count) in enumerate(page_data, start=start_index + 1):
                member = inter.guild.get_member(user_id)
                if member:
                    # 제외된 역할 정보 추가
                    excluded_role_names = [role.name for role in member.roles if role.id in excluded_roles]
                    role_text = f" (역할: {', '.join(excluded_role_names)})"
                    
                    # 현재 사용자 강조
                    if member.id == command_user.id:
                        name_text = f"**`{index}등.` {member.mention} - {count}회{role_text}**"
                    else:
                        name_text = f"`{index}등.` {member.mention} - {count}회{role_text}"
                        
                    leaderboard_text += name_text + "\n"
        else:
            leaderboard_text = "제외된 역할을 가진 사용자가 없습니다."
            
        embed.description = f"총 {total_excluded}명의 제외된 역할 사용자\n\n" + leaderboard_text
        
        # 현재 페이지에 사용자가 없고 자신이 제외된 역할을 가졌다면 하단에 표시
        if command_user.id not in [uid for uid, _ in page_data] and any(role.id in excluded_roles for role in command_user.roles):
            # 전체 리스트에서 사용자의 순위 찾기
            user_position = next((i + 1 for i, (uid, _) in enumerate(excluded_members) if uid == command_user.id), None)
            if user_position:
                leaderboard_text += "\n─────────────────\n"
                leaderboard_text += f"**나의 순위: `{user_position}등` - {user_count}회**"
                embed.description = f"총 {total_excluded}명의 제외된 역할 사용자\n\n" + leaderboard_text
        
        # 마지막 집계 시간 표시
        last_aggregate_date = None
        if db.is_mongo_connected():
            last_aggregate_date = db.get_last_aggregate_date(self.guild_id)
        
        if last_aggregate_date:
            kst = pytz.timezone('Asia/Seoul')
            last_aggregate_date_kst = last_aggregate_date.astimezone(kst)
            formatted_time = last_aggregate_date_kst.strftime("%Y년 %m월 %d일 %p %I시 %M분 %S초").replace('PM', '오후').replace('AM', '오전')
            embed.set_footer(text=f"마지막 집계: {formatted_time}")
        
        # 버튼 활성화 상태 설정
        self.children[0].disabled = self.current_page == 1  # 이전 버튼
        self.children[1].disabled = self.current_page == self.max_page  # 다음 버튼
        
        # 임베드 전송/업데이트
        try:
            if inter.response.is_done():
                await inter.edit_original_message(embed=embed, view=self)
            else:
                await inter.response.edit_message(embed=embed, view=self)
        except Exception as e:
            print(f"Error updating admin leaderboard: {e}")
            await inter.followup.send(embed=embed, view=self)

    @disnake.ui.button(label="이전", style=disnake.ButtonStyle.primary)
    async def previous_page(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return

        if self.current_page > 1:
            self.current_page -= 1
            await self.update_page(inter)

    @disnake.ui.button(label="다음", style=disnake.ButtonStyle.primary)
    async def next_page(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return

        if self.current_page < self.max_page:
            self.current_page += 1
            await self.update_page(inter)

# 권한 체크 함수
def has_admin_permission(inter):
    """사용자가 관리자이거나 제외된 역할을 가졌는지 확인합니다."""
    # 관리자 권한 체크
    if inter.author.guild_permissions.administrator:
        return True
    
    # 제외된 역할 체크
    guild_id = inter.guild.id
    excluded_roles = server_excluded_roles.get(guild_id, [])
    return any(role.id in excluded_roles for role in inter.author.roles)

@bot.slash_command(name="리더보드관리자", description="제외된 역할을 가진 서버 사용자의 채팅 순위를 보여주는 것이다.")
async def 리더보드관리자(inter: disnake.ApplicationCommandInteraction):
    # 권한 체크
    if not has_admin_permission(inter):
        await inter.response.send_message(
            "❌ 이 명령어는 서버 관리자 또는 제외된 역할을 가진 사용자만 사용할 수 있는 것이다.",
            ephemeral=True
        )
        return
    
    guild_id = inter.guild.id
    
    # 데이터 확인
    if guild_id not in server_chat_counts or not server_chat_counts[guild_id]:
        await inter.response.send_message(
            "❌ 채팅 데이터가 없는 것이다. 아직 채팅이 기록되지 않았거나 모두 삭제된 것이다.",
            ephemeral=True
        )
        return
    
    # 제외된 역할 확인
    excluded_roles = server_excluded_roles.get(guild_id, [])
    if not excluded_roles:
        await inter.response.send_message(
            "❌ 설정된 제외 역할이 없는 것이다. `/역할제외 추가` 명령어로 먼저 제외 역할을 설정해야 하는 것이다.",
            ephemeral=True
        )
        return
    
    # 리더보드 뷰 생성 및 응답
    try:
        view = AdminLeaderboardView(inter.author.id, guild_id)
        await inter.response.send_message("관리자용 리더보드를 불러오는 중인 것이다...", view=view)
        await view.update_page(inter)
    except Exception as e:
        print(f"Admin leaderboard error: {e}")
        import traceback
        traceback.print_exc()
        await inter.followup.send(
            "❌ 리더보드를 불러오는 중 오류가 발생한 것이다. 다시 시도해보는 것이다.",
            ephemeral=True
        )
