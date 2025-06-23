from disnake.ext import commands
import disnake
from disnake.ui import Button, View
from bot import bot, server_chat_counts, server_excluded_roles
import database as db
import pytz
from collections import Counter

class AdminLeaderboardView(disnake.ui.View):
    def __init__(self, author_id, guild_id, current_page=1):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.current_page = current_page
        self.author_id = author_id
        self.chat_counts = server_chat_counts[self.guild_id]
        
        # 모든 사용자 포함
        sorted_chatters = sorted(self.chat_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 페이지당 25명으로 설정
        self.items_per_page = 25
        self.max_page = (len(sorted_chatters) - 1) // self.items_per_page + 1
        
        # 명령어 사용자의 순위 찾기
        self.user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_chatters) if uid == author_id), None)
        if self.user_rank:
            self.user_page = (self.user_rank - 1) // self.items_per_page + 1
        else:
            self.user_page = None

    async def update_page(self, inter):
        chat_counts = self.chat_counts
        # 모든 사용자를 포함하여 정렬
        sorted_chatters = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)

        # 제외된 역할을 가진 사용자만 필터링
        excluded_roles = server_excluded_roles.get(self.guild_id, [])
        excluded_members = []
        
        # 각 사용자가 제외된 역할을 가지고 있는지 확인
        for user_id, count in sorted_chatters:
            member = inter.guild.get_member(user_id)
            if member and any(role.id in excluded_roles for role in member.roles):
                excluded_members.append((user_id, count))
        
        # 페이지네이션 조정
        total_excluded = len(excluded_members)
        self.max_page = (total_excluded - 1) // self.items_per_page + 1 if total_excluded > 0 else 1
        self.current_page = min(self.current_page, self.max_page)
        
        # 현재 페이지에 표시할 제외된 역할 사용자 목록
        page_start = (self.current_page - 1) * self.items_per_page
        page_end = page_start + self.items_per_page
        page_data = excluded_members[page_start:page_end]

        # 임베드 생성
        embed = disnake.Embed(title="관리자용 리더보드 (제외된 역할만)", color=disnake.Color.red())
        leaderboard_text = ""

        command_user = inter.author  # 명령어 사용자 저장
        
        # 명령어 사용자의 순위 찾기
        user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_chatters) if uid == command_user.id), None)
        user_count = chat_counts.get(command_user.id, 0)

        # 제외된 사용자 목록 표시
        for index, (user_id, count) in enumerate(page_data, start=page_start + 1):
            member = inter.guild.get_member(user_id)
            if member:
                # 제외된 역할 이름 목록 생성
                excluded_role_names = [role.name for role in member.roles if role.id in excluded_roles]
                role_text = f" (제외 역할: {', '.join(excluded_role_names)})"
                
                # 사용자 정보 표시 개선
                if member.id == command_user.id:
                    name_text = f"**`{index}등.` {member.mention} - {count}회{role_text}**"
                else:
                    name_text = f"`{index}등.` {member.mention} - {count}회{role_text}"
                
                leaderboard_text += name_text + "\n"

        # 리스트가 비어있는 경우 안내 메시지
        if not page_data:
            leaderboard_text = "제외된 역할을 가진 사용자가 없습니다."
            
        # 전체 제외된 사용자 수 표시
        embed.description = f"총 {total_excluded}명의 제외된 역할 사용자\n\n" + leaderboard_text

        # 마지막 집계 시간을 한국 시간으로 변환하고 포맷 변경
        last_aggregate_date = None
        if db.is_mongo_connected():
            last_aggregate_date = db.get_last_aggregate_date(self.guild_id)
        
        if last_aggregate_date:
            kst = pytz.timezone('Asia/Seoul')
            last_aggregate_date_kst = last_aggregate_date.astimezone(kst)
            formatted_time = last_aggregate_date_kst.strftime("%Y년 %m월 %d일 %p %I시 %M분 %S초").replace('PM', '오후').replace('AM', '오전')
            embed.set_footer(text=f"마지막 집계: {formatted_time}")

        # 버튼 상태 업데이트
        self.children[0].disabled = self.current_page == 1  # 이전 버튼
        self.children[1].disabled = self.current_page == self.max_page  # 다음 버튼

        try:
            if inter.response.is_done():
                await inter.edit_original_message(embed=embed, view=self)
            else:
                await inter.response.edit_message(embed=embed, view=self)
        except Exception as e:
            print(f"Error updating admin leaderboard page: {e}")
            # 오류 발생 시 새 메시지로 응답
            await inter.followup.send(embed=embed, view=self)

    @disnake.ui.button(label="이전", style=disnake.ButtonStyle.primary)
    async def previous_page(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        # 버튼 사용자 권한 확인
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return

        if self.current_page > 1:
            self.current_page -= 1
            await self.update_page(inter)

    @disnake.ui.button(label="다음", style=disnake.ButtonStyle.primary)
    async def next_page(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        # 버튼 사용자 권한 확인
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return

        if self.current_page < self.max_page:
            self.current_page += 1
            await self.update_page(inter)

# 관리자 권한 및 제외된 역할 체크 함수
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
    
    # 뷰 생성 및 페이지 표시
    view = AdminLeaderboardView(inter.author.id, guild_id)
    await inter.response.send_message("관리자용 리더보드를 불러오는 중인 것이다...", view=view)
    await view.update_page(inter)
