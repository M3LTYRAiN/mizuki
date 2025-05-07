from disnake.ext import commands
import disnake
from disnake.ui import Button, View
from bot import bot, server_chat_counts, server_excluded_roles, get_last_aggregate_date
import pytz  # Add this import for timezone handling

class LeaderboardView(View):
    def __init__(self, author_id, guild_id, current_page=1):  # author_id 추가
        super().__init__()
        self.guild_id = guild_id
        self.current_page = current_page
        self.author_id = author_id  # 명령어 사용자 ID 저장
        self.chat_counts = server_chat_counts[self.guild_id]
        sorted_chatters = sorted(self.chat_counts.items(), key=lambda x: x[1], reverse=True)
        self.max_page = (len(sorted_chatters) - 1) // 50 + 1
        
        # 명령어 사용자의 순위 찾기
        self.user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_chatters) if uid == author_id), None)
        if self.user_rank:
            self.user_page = (self.user_rank - 1) // 50 + 1
        else:
            self.user_page = None

    async def update_page(self, inter):
        chat_counts = self.chat_counts
        sorted_chatters = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)

        start_index = (self.current_page - 1) * 50
        end_index = self.current_page * 50
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
                excluded = any(role.id in excluded_roles for role in member.roles)
                
                # 명령어 사용자인 경우 강조
                if member.id == command_user.id:
                    leaderboard_text += f"**`{index}등.` {member.mention} - {count}회**"
                else:
                    leaderboard_text += f"`{index}등.` {member.mention} - {count}회"
                
                if excluded:
                    leaderboard_text += " (제외됨)"
                leaderboard_text += "\n"

        # 현재 페이지에 명령어 사용자가 없는 경우, 하단에 사용자 정보 표시
        if not any(uid == command_user.id for uid, _ in page_data) and user_rank is not None:
            leaderboard_text += "\n─────────────────\n"
            leaderboard_text += f"**나의 순위: `{user_rank}등` - {user_count}회**"

        embed.description = leaderboard_text

        # 마지막 집계 시간을 한국 시간으로 변환하고 포맷 변경
        last_aggregate_date = get_last_aggregate_date(self.guild_id)
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

@bot.slash_command(name="리더보드", description="서버의 채팅 순위 리더보드를 보여주는 것이다.")
async def 리더보드(inter: disnake.ApplicationCommandInteraction):
    guild_id = inter.guild.id
    if guild_id not in server_chat_counts or not server_chat_counts[guild_id]:
        await inter.response.send_message("❌ 채팅 데이터가 없는 것이다.", ephemeral=True)
        return

    view = LeaderboardView(inter.author.id, guild_id)  # author_id 전달
    await inter.response.send_message("리더보드를 불러오는 중인 것이다...", view=view)
    await view.update_page(inter)
