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
        self.author_id = author_id  # 명령어 사용자 ID 저장
        self.chat_counts = server_chat_counts[self.guild_id]
        
        # 모든 사용자의 채팅 데이터 로드 (필터링은 update_page에서)
        sorted_chatters = sorted(self.chat_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 페이지당 25명으로 설정
        self.items_per_page = 25
        self.max_page = 1  # 초기값, update_page에서 다시 계산
        
        # 명령어 사용자의 순위 찾기
        self.user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_chatters) if uid == author_id), None)
        if self.user_rank:
            self.user_page = (self.user_rank - 1) // self.items_per_page + 1
        else:
            self.user_page = None

    async def update_page(self, inter):
        # 서버의 모든 채팅 데이터
        chat_counts = self.chat_counts
        
        # 디버깅 정보: 서버 채팅 데이터 상태 확인
        print(f"[관리자리더보드] 서버 {self.guild_id} 전체 사용자 수: {len(chat_counts)}")
        
        # 제외된 역할 목록 가져오기
        excluded_roles = server_excluded_roles.get(self.guild_id, [])
        
        print(f"[관리자리더보드] 제외 역할 ID: {excluded_roles}")
        
        # 제외된 역할을 가진 사용자들만 필터링
        excluded_members_data = []
        
        for user_id, count in chat_counts.items():
            member = inter.guild.get_member(user_id)
            if member and any(role.id in excluded_roles for role in member.roles):
                excluded_members_data.append((user_id, count))
                
                # 디버깅: 제외된 사용자 정보
                role_names = [role.name for role in member.roles if role.id in excluded_roles]
                print(f"[관리자리더보드] 제외된 사용자: {member.display_name}, 채팅 수: {count}, 역할: {role_names}")
        
        # 채팅 수 기준으로 정렬
        excluded_members_data.sort(key=lambda x: x[1], reverse=True)
        
        # 전체 제외된 사용자 수
        total_excluded = len(excluded_members_data)
        
        print(f"[관리자리더보드] 제외된 사용자 총 {total_excluded}명")
        
        # 페이지네이션 계산
        self.max_page = max(1, (total_excluded + self.items_per_page - 1) // self.items_per_page)
        self.current_page = max(1, min(self.current_page, self.max_page))
        
        # 현재 페이지에 표시할 사용자들
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = min(start_index + self.items_per_page, total_excluded)
        page_data = excluded_members_data[start_index:end_index]
        
        # 임베드 생성 (빨간색 사용)
        embed = disnake.Embed(
            title="관리자용 리더보드 (제외된 역할만)",
            color=disnake.Color.red()
        )
        
        leaderboard_text = ""
        
        # 명령어 사용자 정보
        command_user = inter.author
        user_count = chat_counts.get(command_user.id, 0)
        
        # 제외된 사용자 중 명령어 사용자의 순위 찾기
        user_rank_excluded = next(
            (i + 1 for i, (uid, _) in enumerate(excluded_members_data) if uid == command_user.id),
            None
        )
        
        # 현재 페이지 사용자 목록 표시
        for index, (user_id, count) in enumerate(page_data, start=start_index + 1):
            member = inter.guild.get_member(user_id)
            if member:
                # 제외된 역할 이름 표시
                excluded_role_names = [role.name for role in member.roles if role.id in excluded_roles]
                role_text = f" (제외 역할: {', '.join(excluded_role_names)})"
                
                # 명령어 사용자 강조
                if member.id == command_user.id:
                    name_text = f"**`{index}등.` {member.mention} - {count}회{role_text}**"
                else:
                    name_text = f"`{index}등.` {member.mention} - {count}회{role_text}"
                
                leaderboard_text += name_text + "\n"
        
        # 리더보드가 비어있는 경우
        if not page_data:
            leaderboard_text = "제외된 역할을 가진 사용자가 없습니다."
        
        # 현재 페이지에 명령어 사용자가 없고, 제외된 역할을 가진 경우 아래에 표시
        if not any(uid == command_user.id for uid, _ in page_data) and user_rank_excluded is not None:
            leaderboard_text += "\n─────────────────\n"
            
            # 제외된 역할 이름 표시
            excluded_role_names = [role.name for role in command_user.roles if role.id in excluded_roles]
            role_text = f" (제외 역할: {', '.join(excluded_role_names)})"
            
            leaderboard_text += f"**나의 순위: `{user_rank_excluded}등` - {user_count}회{role_text}**"
        
        # 임베드에 내용 추가
        embed.description = f"총 {total_excluded}명의 제외된 역할 사용자\n\n{leaderboard_text}"
        
        # 마지막 집계 날짜 표시
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
        if len(self.children) > 2:  # '나' 버튼이 있으면
            self.children[2].disabled = user_rank_excluded is None
        
        # 임베드 업데이트
        try:
            if inter.response.is_done():
                await inter.edit_original_message(embed=embed, view=self)
            else:
                await inter.response.edit_message(embed=embed, view=self)
        except Exception as e:
            print(f"Error updating admin leaderboard: {e}")
            await inter.followup.send(embed=embed, view=self)

    @disnake.ui.button(label="이전", style=disnake.ButtonStyle.primary)
    async def previous_page(self, button: Button, inter: disnake.MessageInteraction):
        # 버튼 사용자 확인
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return

        if self.current_page > 1:
            self.current_page -= 1
            await self.update_page(inter)

    @disnake.ui.button(label="다음", style=disnake.ButtonStyle.primary)
    async def next_page(self, button: Button, inter: disnake.MessageInteraction):
        # 버튼 사용자 확인
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return

        if self.current_page < self.max_page:
            self.current_page += 1
            await self.update_page(inter)

    @disnake.ui.button(label="나", style=disnake.ButtonStyle.success)
    async def my_page(self, button: Button, inter: disnake.MessageInteraction):
        # 버튼 사용자 확인
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return
        
        # 제외된 역할을 가진 사용자만 필터링
        excluded_roles = server_excluded_roles.get(self.guild_id, [])
        excluded_members_data = []
        
        for user_id, count in self.chat_counts.items():
            member = inter.guild.get_member(user_id)
            if member and any(role.id in excluded_roles for role in member.roles):
                excluded_members_data.append((user_id, count))
                
        # 채팅 수 기준으로 정렬
        excluded_members_data.sort(key=lambda x: x[1], reverse=True)
        
        # 사용자 위치 찾기
        user_index = next((i for i, (uid, _) in enumerate(excluded_members_data) if uid == inter.author.id), None)
        
        if user_index is not None:
            # 사용자가 있는 페이지로 이동
            self.current_page = (user_index // self.items_per_page) + 1
            await self.update_page(inter)
        else:
            await inter.response.send_message("당신은 제외된 역할을 가지고 있지 않은 것이다!", ephemeral=True)

# 관리자 또는 제외된 역할을 가진 사용자인지 확인
def is_admin_or_excluded(inter):
    """사용자가 관리자이거나 제외된 역할을 가졌는지 확인"""
    if inter.author.guild_permissions.administrator:
        return True
        
    # 제외된 역할 목록
    excluded_roles = server_excluded_roles.get(inter.guild.id, [])
    
    # 사용자가 제외된 역할을 가지고 있는지 확인
    for role in inter.author.roles:
        if role.id in excluded_roles:
            return True
            
    return False

@bot.slash_command(
    name="리더보드관리자", 
    description="제외된 역할을 가진 사용자들의 채팅 순위를 보는 특별 리더보드입니다."
)
async def 리더보드관리자(inter: disnake.ApplicationCommandInteraction):
    # 권한 체크: 관리자 또는 제외된 역할을 가진 사용자만 사용 가능
    if not is_admin_or_excluded(inter):
        await inter.response.send_message(
            "❌ 이 명령어는 관리자 또는 제외된 역할을 가진 사용자만 사용할 수 있는 것이다!", 
            ephemeral=True
        )
        return
    
    guild_id = inter.guild.id
    
    # 디버그 메시지
    print(f"[관리자리더보드] 명령어 실행: 서버 {inter.guild.name} ({guild_id}), 사용자 {inter.author.name}")
    
    # 서버 채팅 데이터 확인
    if guild_id not in server_chat_counts or not server_chat_counts[guild_id]:
        try:
            # DB에서 채팅 데이터 로드 시도
            if db.is_mongo_connected():
                guild_chat_counts = db.get_guild_chat_counts(guild_id)
                
                if guild_chat_counts:
                    server_chat_counts[guild_id] = Counter(guild_chat_counts)
                    print(f"[관리자리더보드] 서버 {guild_id}의 채팅 데이터 로드: {len(guild_chat_counts)}개")
                else:
                    await inter.response.send_message(
                        "❌ 채팅 데이터가 없는 것이다.", 
                        ephemeral=True
                    )
                    return
            else:
                await inter.response.send_message(
                    "❌ 데이터베이스에 연결할 수 없는 것이다.", 
                    ephemeral=True
                )
                return
        except Exception as e:
            await inter.response.send_message(
                f"❌ 오류가 발생했다: {e}", 
                ephemeral=True
            )
            return
    
    # 서버에 제외된 역할이 설정되어 있는지 확인
    if guild_id not in server_excluded_roles or not server_excluded_roles[guild_id]:
        await inter.response.send_message(
            "❌ 이 서버에는 제외된 역할이 설정되어 있지 않다. 먼저 `/역할제외 추가` 명령어로 제외할 역할을 설정해야 한다.", 
            ephemeral=True
        )
        return
    
    # 제외된 역할을 가진 사용자가 있는지 확인
    excluded_roles = server_excluded_roles[guild_id]
    has_excluded_members = False
    
    for member in inter.guild.members:
        if any(role.id in excluded_roles for role in member.roles):
            has_excluded_members = True
            break
    
    if not has_excluded_members:
        await inter.response.send_message(
            "❌ 제외된 역할을 가진 사용자가 서버에 없는 것이다!", 
            ephemeral=True
        )
        return
    
    # 리더보드 표시
    view = AdminLeaderboardView(inter.author.id, guild_id)
    await inter.response.send_message(
        "관리자용 리더보드를 불러오는 중인 것이다...", 
        view=view
    )
    await view.update_page(inter)
