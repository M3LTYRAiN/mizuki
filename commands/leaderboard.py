from disnake.ext import commands
import disnake
from disnake.ui import Button, View
from bot import bot, server_chat_counts, server_excluded_roles
import database as db
import pytz  # Add this import for timezone handling
from collections import Counter  # Counter 명시적 임포트 추가

class LeaderboardView(View):
    def __init__(self, author_id, guild_id, current_page=1):  # author_id 추가
        super().__init__()
        self.guild_id = guild_id
        self.current_page = current_page
        self.author_id = author_id  # 명령어 사용자 ID 저장
        self.chat_counts = server_chat_counts[self.guild_id]
        
        # 순위 계산 시 제외 역할을 필터링하지 않음 (변경된 부분)
        sorted_chatters = sorted(self.chat_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 페이지당 25명으로 변경 (50명에서)
        self.items_per_page = 25
        self.max_page = (len(sorted_chatters) - 1) // self.items_per_page + 1
        
        # 명령어 사용자의 순위 찾기
        self.user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_chatters) if uid == author_id), None)
        if self.user_rank:
            # 페이지당 25명으로 계산 (50명에서 변경)
            self.user_page = (self.user_rank - 1) // self.items_per_page + 1
        else:
            self.user_page = None

    async def update_page(self, inter):
        chat_counts = self.chat_counts
        # 모든 사용자 포함하여 정렬 (제외 역할 필터링 없음)
        sorted_chatters = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)

        # 페이지당 25명으로 변경 (50명에서)
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = self.current_page * self.items_per_page
        page_data = sorted_chatters[start_index:end_index]

        embed = disnake.Embed(title="리더보드", color=disnake.Color.green())
        leaderboard_text = ""

        excluded_roles = server_excluded_roles.get(self.guild_id, [])
        command_user = inter.author  # 명령어 사용자 저장

        # 명령어 사용자의 순위 찾기
        user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_chatters) if uid == command_user.id), None)
        user_count = chat_counts.get(command_user.id, 0)

        for index, (user_id, count) in enumerate(page_data, start=start_index + 1):
            member = inter.guild.get_member(user_id)
            if member:
                # 제외 역할 여부 확인
                excluded = any(role.id in excluded_roles for role in member.roles)
                
                # 사용자를 강조할지 결정
                if member.id == command_user.id:
                    name_text = f"**`{index}등.` {member.mention} - {count}회"
                    if excluded:
                        name_text += " (제외됨)**"
                    else:
                        name_text += "**"
                else:
                    name_text = f"`{index}등.` {member.mention} - {count}회"
                    if excluded:
                        name_text += " (제외됨)"
                
                leaderboard_text += name_text + "\n"

        # 현재 페이지에 명령어 사용자가 없는 경우, 하단에 사용자 정보 표시
        if not any(uid == command_user.id for uid, _ in page_data) and user_rank is not None:
            leaderboard_text += "\n─────────────────\n"
            
            # 자신이 제외 역할인지 확인
            self_excluded = any(role.id in excluded_roles for role in command_user.roles)
            exclude_text = " (제외됨)" if self_excluded else ""
            
            leaderboard_text += f"**나의 순위: `{user_rank}등` - {user_count}회{exclude_text}**"

        embed.description = leaderboard_text

        # 마지막 집계 시간을 한국 시간으로 변환하고 포맷 변경
        last_aggregate_date = None
        if db.is_mongo_connected():
            last_aggregate_date = db.get_last_aggregate_date(self.guild_id)
        
        if last_aggregate_date:
            kst = pytz.timezone('Asia/Seoul')
            last_aggregate_date_kst = last_aggregate_date.astimezone(kst)
            formatted_time = last_aggregate_date_kst.strftime("%Y년 %m월 %d일 %p %I시 %M분 %S초").replace('PM', '오후').replace('AM', '오전')
            embed.set_footer(text=f"마지막 집계: {formatted_time}")

        # 버튼 상태 업데이트 수정
        self.children[0].disabled = self.current_page == 1  # 이전 버튼
        self.children[1].disabled = self.current_page == self.max_page  # 다음 버튼
        # 나 버튼은 항상 활성화 상태 유지

        try:
            if inter.response.is_done():
                await inter.edit_original_message(embed=embed, view=self)
            else:
                await inter.response.edit_message(embed=embed, view=self)
        except Exception as e:
            print(f"Error updating page: {e}")
            # 오류 발생 시 새 메시지로 응답
            await inter.followup.send(embed=embed, view=self)

    @disnake.ui.button(label="이전", style=disnake.ButtonStyle.primary)
    async def previous_page(self, button: Button, inter: disnake.MessageInteraction):
        # 버튼 사용자 권한 확인
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return

        if self.current_page > 1:
            self.current_page -= 1
            await self.update_page(inter)

    @disnake.ui.button(label="다음", style=disnake.ButtonStyle.primary)
    async def next_page(self, button: Button, inter: disnake.MessageInteraction):
        # 버튼 사용자 권한 확인
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return

        if self.current_page < self.max_page:
            self.current_page += 1
            await self.update_page(inter)

    @disnake.ui.button(label="나", style=disnake.ButtonStyle.success)
    async def my_page(self, button: Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.author_id:
            await inter.response.send_message("다른 사람의 리더보드 버튼은 조작할 수 없는 것이다!", ephemeral=True)
            return

        if self.user_page:
            try:
                self.current_page = self.user_page
                await inter.response.defer()  # 응답 지연 추가
                await self.update_page(inter)
            except Exception as e:
                await inter.followup.send("페이지 이동 중 오류가 발생한 것이다...", ephemeral=True)
        else:
            await inter.response.send_message("아직 채팅 기록이 없는 것이다.", ephemeral=True)

# 관리자용 리더보드 뷰 클래스 추가
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

        # 페이지당 25명으로 설정
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = self.current_page * self.items_per_page
        
        # 제외된 역할을 가진 사용자만 필터링 (중요 변경 부분)
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

@bot.slash_command(name="리더보드", description="서버의 채팅 순위 리더보드를 보여주는 것이다.")
async def 리더보드(inter: disnake.ApplicationCommandInteraction):
    guild_id = inter.guild.id
    
    # 데이터 확인 로직을 개선하여 더 정확한 정보 제공
    has_chat_data = False
    
    # MongoDB 연결 확인
    if not db.is_mongo_connected():
        await inter.response.send_message("⚠️ MongoDB에 연결되어 있지 않아 채팅 데이터를 확인할 수 없는 것이다.", ephemeral=True)
        return
    
    # 메모리 캐시 디버깅
    print(f"[리더보드] 서버 상태 확인:")
    print(f"  - 현재 메모리에 있는 서버 목록: {list(server_chat_counts.keys())}")
    print(f"  - 요청한 서버 ID: {guild_id}")
    
    # 1. 메모리 캐시 확인
    if guild_id in server_chat_counts and server_chat_counts[guild_id]:
        has_chat_data = True
        chat_count = len(server_chat_counts[guild_id])
        print(f"[리더보드] 서버 {guild_id}의 메모리에 채팅 데이터 있음: {chat_count}명의 사용자")
        
        # 메모리에 있는 데이터 샘플 출력 (첫 3개)
        top_users = sorted(server_chat_counts[guild_id].items(), key=lambda x: x[1], reverse=True)[:3]
        for user_id, count in top_users:
            print(f"  - 사용자 {user_id}: {count}회")
    else:
        print(f"[리더보드] 서버 {guild_id}의 메모리에 채팅 데이터 없음, MongoDB에서 확인 시도")
        
        # 2. MongoDB에서 직접 데이터 확인
        try:
            # 해당 길드의 채팅 데이터가 있는지 확인
            chat_count = db.chat_counts_collection.count_documents({"guild_id": guild_id})
            print(f"[리더보드] MongoDB에서 서버 {guild_id}의 문서 수: {chat_count}")
            
            if chat_count > 0:
                has_chat_data = True
                print(f"[리더보드] MongoDB에서 서버 {guild_id}의 채팅 데이터 확인: {chat_count}개 항목")
                
                # 데이터를 메모리에 로드 (Counter 객체 명시적 생성)
                if guild_id not in server_chat_counts:
                    server_chat_counts[guild_id] = Counter()
                    
                cursor = db.chat_counts_collection.find({"guild_id": guild_id})
                loaded_count = 0
                
                for doc in cursor:
                    user_id = doc.get("user_id")
                    count = doc.get("count", 0)
                    
                    if user_id:  # user_id가 있는 경우만 처리
                        server_chat_counts[guild_id][user_id] = count
                        loaded_count += 1
                
                print(f"[리더보드] MongoDB에서 서버 {guild_id}의 채팅 데이터 {loaded_count}개 로드됨")
                
                # 로딩 후 다시 확인
                if len(server_chat_counts[guild_id]) > 0:
                    print(f"[리더보드] 데이터 로드 확인: {len(server_chat_counts[guild_id])}개 항목")
                    has_chat_data = True
                else:
                    print(f"[리더보드] 데이터 로드 실패: 0개 항목")
                    has_chat_data = False
            else:
                print(f"[리더보드] MongoDB에도 서버 {guild_id}의 채팅 데이터가 없음")
        except Exception as e:
            print(f"[리더보드] MongoDB 조회 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    # 채팅 데이터가 없는 경우
    if not has_chat_data or guild_id not in server_chat_counts or not server_chat_counts[guild_id]:
        # 디버그 정보 수집
        debug_info = []
        debug_info.append(f"서버 ID: {guild_id}")
        debug_info.append(f"메모리 캐시 포함 여부: {'O' if guild_id in server_chat_counts else 'X'}")
        
        try:
            if guild_id in server_chat_counts:
                debug_info.append(f"메모리에 있는 항목 수: {len(server_chat_counts[guild_id])}")
            
            # 직접 DB에서 카운트 확인
            db_count = db.chat_counts_collection.count_documents({"guild_id": guild_id})
            debug_info.append(f"DB에 있는 항목 수: {db_count}")
        except Exception as e:
            debug_info.append(f"디버그 정보 수집 중 오류: {e}")
        
        debug_text = "\n".join(debug_info)
        print(f"[리더보드] 디버그 정보:\n{debug_text}")
        
        # 더 자세한 오류 메시지 제공
        await inter.response.send_message(
            "❌ 채팅 데이터가 없는 것이다. 다음 사항을 확인하는 것이다:\n"
            "1. 봇이 채팅을 집계한 적이 있는지\n"
            "2. 모든 채팅이 제외 역할에 의해 무시되지 않는지\n"
            "3. 봇이 재시작된 후 채팅이 있었는지\n\n"
            f"디버그 정보: ```\n{debug_text}\n```",
            ephemeral=True
        )
        return
    
    # 클래스가 Counter가 맞는지 확인
    counter_class = type(server_chat_counts[guild_id]).__name__
    print(f"[리더보드] server_chat_counts[{guild_id}]의 타입: {counter_class}")
    
    # 만약 Counter 객체가 아니라면 변환
    if counter_class != "Counter":
        print(f"[리더보드] Counter 객체가 아니므로 변환합니다: {counter_class}")
        server_chat_counts[guild_id] = Counter(server_chat_counts[guild_id])

    # 데이터가 있는 경우 리더보드 표시 계속
    view = LeaderboardView(inter.author.id, guild_id)
    await inter.response.send_message("리더보드를 불러오는 중인 것이다...", view=view)
    await view.update_page(inter)

# 새로운 관리자용 리더보드 명령어 추가
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
