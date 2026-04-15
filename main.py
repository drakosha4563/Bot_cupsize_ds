import sqlite3
import time
import discord
from discord.ext import commands
from discord import app_commands
import re
from datetime import datetime
load_dotenv()

CUPSIZE_COLOR = 0x9b59b6
DB_PATH = 'users.db'
DEFAULT_RANK = '1 - Test'

RANKS = [
    "1 - Test", "2 - Farmer", "3 - Jn. Main", "4 - Main",
    "5 - Recruit", "6 - High Rank", "7 - Dep. Leader", "Leader"
]


class DB:
    @staticmethod
    def execute(query: str, params: tuple = ()) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(query, params)

    @staticmethod
    def fetchall(query: str, params: tuple = ()) -> list:
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute(query, params).fetchall()

    @staticmethod
    def fetchone(query: str, params: tuple = ()) -> tuple:
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute(query, params).fetchone()


def init_db() -> None:
    DB.execute('''CREATE TABLE IF NOT EXISTS users
                  (
                      user_id
                      INTEGER
                      PRIMARY
                      KEY,
                      majestic_static
                      INTEGER,
                      character_name
                      TEXT,
                      gender
                      TEXT,
                      rank
                      TEXT
                      DEFAULT
                      '1 - Test',
                      reports_count
                      INTEGER
                      DEFAULT
                      0
                  )''')
    DB.execute('''CREATE TABLE IF NOT EXISTS nvs_records
                  (
                      id
                      INTEGER
                      PRIMARY
                      KEY
                      AUTOINCREMENT,
                      user_id
                      INTEGER,
                      reason
                      TEXT,
                      date
                      TEXT
                  )''')
    DB.execute('''CREATE TABLE IF NOT EXISTS afk_requests
                  (
                      id
                      INTEGER
                      PRIMARY
                      KEY
                      AUTOINCREMENT,
                      user_id
                      INTEGER,
                      reason
                      TEXT,
                      start_time
                      TEXT,
                      end_time
                      TEXT,
                      status
                      TEXT
                      DEFAULT
                      'pending'
                  )''')
    DB.execute('''CREATE TABLE IF NOT EXISTS reports
                  (
                      id
                      INTEGER
                      PRIMARY
                      KEY
                      AUTOINCREMENT,
                      user_id
                      INTEGER,
                      event_name
                      TEXT,
                      date
                      TEXT,
                      comment
                      TEXT,
                      image_url
                      TEXT,
                      status
                      TEXT
                      DEFAULT
                      'pending'
                  )''')
    DB.execute('''CREATE TABLE IF NOT EXISTS nvs_removals
                  (
                      id
                      INTEGER
                      PRIMARY
                      KEY
                      AUTOINCREMENT,
                      user_id
                      INTEGER,
                      nvs_index
                      TEXT,
                      comment
                      TEXT,
                      image_url
                      TEXT,
                      status
                      TEXT
                      DEFAULT
                      'pending'
                  )''')
    DB.execute('''CREATE TABLE IF NOT EXISTS events
                  (
                      id
                      INTEGER
                      PRIMARY
                      KEY
                      AUTOINCREMENT,
                      title
                      TEXT,
                      start_time
                      TEXT,
                      comment
                      TEXT,
                      created_timestamp
                      REAL
                  )''')


def is_registered(user_id: int) -> bool:
    return DB.fetchone('SELECT user_id FROM users WHERE user_id = ?', (user_id,)) is not None


def get_nvs_count(user_id: int) -> int:
    res = DB.fetchone('SELECT COUNT(*) FROM nvs_records WHERE user_id = ?', (user_id,))
    return res[0] if res else 0


async def notify_user(interaction: discord.Interaction, target_id: int, message: str, embed: discord.Embed = None):
    user = interaction.client.get_user(target_id)
    if user:
        try:
            await user.send(message, embed=embed)
        except discord.Forbidden:
            pass


def get_main_menu_embed() -> discord.Embed:
    embed = discord.Embed(
        title="💠 Планшет семьи Cupsize",
        description="Добро пожаловать в главную панель управления.\nВыберите нужный раздел ниже:",
        color=CUPSIZE_COLOR
    )
    embed.set_footer(text="Cupsize Family • Majestic RP")
    return embed


async def send_stub(interaction: discord.Interaction, title: str, view_to_return: discord.ui.View) -> None:
    embed = discord.Embed(
        title="В разработке",
        description=f"🚧 Раздел **«{title}»** скоро будет доступен.",
        color=discord.Color.orange()
    )
    await interaction.response.edit_message(embed=embed, view=view_to_return)


class ReturnToMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="🔙 Назад в меню", style=discord.ButtonStyle.danger)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_main_menu_embed(), view=MainMenuView(self.user_id))


class ReturnToAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔙 Вернуться в Админку", style=discord.ButtonStyle.danger)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛡️ Админ Панель", description="Выберите раздел для модерирования.",
                              color=discord.Color.dark_red())
        await interaction.response.edit_message(embed=embed, view=AdminPanelView())


class ReturnToInfoView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="🔙 Назад к информации", style=discord.ButtonStyle.danger)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="ℹ️ Информационный центр", description="База знаний семьи.", color=CUPSIZE_COLOR)
        await interaction.response.edit_message(embed=embed, view=InfoMenuView(self.user_id))


class RegistrationModal(discord.ui.Modal, title='Регистрация в базе'):
    static_input = discord.ui.TextInput(label='Твой Статик', style=discord.TextStyle.short, max_length=7)
    name_input = discord.ui.TextInput(label='Имя Фамилия в игре', style=discord.TextStyle.short,
                                      placeholder='Например: Futoshi Cupsize', max_length=32)
    gender_input = discord.ui.TextInput(label='Пол персонажа', style=discord.TextStyle.short, placeholder='М или Ж',
                                        max_length=1)

    async def on_submit(self, interaction: discord.Interaction):
        static_val = self.static_input.value.strip()
        name_val = self.name_input.value.strip()
        gender_val = self.gender_input.value.strip().upper()

        if not static_val.isdigit():
            return await interaction.response.send_message("❌ Ошибка: Статик должен состоять только из цифр!",
                                                           ephemeral=True)
        if not re.match(r"^[A-Za-z\s]+$", name_val):
            return await interaction.response.send_message("❌ Ошибка: Имя должно содержать только английские буквы!",
                                                           ephemeral=True)

        name_parts = name_val.split()
        if len(name_parts) < 2 or name_parts[-1].lower() != 'cupsize':
            return await interaction.response.send_message("❌ Ошибка: Имя должно заканчиваться на фамилию **Cupsize**!",
                                                           ephemeral=True)

        first_name = "".join(name_parts[:-1])
        if len(first_name) < 3:
            return await interaction.response.send_message("❌ Ошибка: Имя слишком короткое (минимум 3 буквы)!",
                                                           ephemeral=True)

        keyboard_mashes = ['asd', 'qwe', 'zxc', 'qwer', 'asdf', 'zxcv', 'wsad']
        if any(mash in first_name.lower() for mash in keyboard_mashes):
            return await interaction.response.send_message("❌ Ошибка: Имя содержит неосмысленный набор букв!",
                                                           ephemeral=True)

        if not any(vowel in first_name.lower() for vowel in 'aeiouy'):
            return await interaction.response.send_message("❌ Ошибка: В имени обязательно должны быть гласные буквы!",
                                                           ephemeral=True)

        if re.search(r"(.)\1\1", first_name.lower()):
            return await interaction.response.send_message("❌ Ошибка: Слишком много одинаковых букв подряд!",
                                                           ephemeral=True)

        if gender_val not in ['М', 'Ж']:
            return await interaction.response.send_message("❌ Ошибка: Пол должен быть указан строго как М или Ж!",
                                                           ephemeral=True)

        formatted_name = " ".join([p.capitalize() for p in name_parts[:-1]]) + " Cupsize"

        DB.execute(
            'INSERT OR REPLACE INTO users (user_id, majestic_static, character_name, gender, rank) VALUES (?, ?, ?, ?, COALESCE((SELECT rank FROM users WHERE user_id = ?), ?))',
            (interaction.user.id, int(static_val), formatted_name, gender_val, interaction.user.id, DEFAULT_RANK)
        )
        embed = get_main_menu_embed()
        embed.description = f"✅ **Успешно!** Профиль **{formatted_name}** ({static_val}) сохранен.\n\n" + embed.description
        await interaction.response.edit_message(embed=embed, view=MainMenuView(interaction.user.id))


class ReportModal(discord.ui.Modal, title='Сдача отчета'):
    event_input = discord.ui.TextInput(label='Название мероприятия', style=discord.TextStyle.short)
    date_input = discord.ui.TextInput(label='Дата (ДД.ММ)', style=discord.TextStyle.short,
                                      placeholder='Например: 15.04')
    comment_input = discord.ui.TextInput(label='Комментарий', style=discord.TextStyle.paragraph, required=False)
    image_input = discord.ui.TextInput(label='Ссылка на док-ва (Imgur, Yapx, YouTube) ', style=discord.TextStyle.short,
                                       placeholder='Вставьте ссылку здесь')

    async def on_submit(self, interaction: discord.Interaction):
        DB.execute(
            'INSERT INTO reports (user_id, event_name, date, comment, image_url) VALUES (?, ?, ?, ?, ?)',
            (interaction.user.id, self.event_input.value, self.date_input.value, self.comment_input.value,
             self.image_input.value)
        )
        await interaction.response.send_message("✅ Ваш отчет отправлен на проверку руководству!", ephemeral=True)


class AFKModal(discord.ui.Modal, title='Заявка на неактив (АФК)'):
    reason_input = discord.ui.TextInput(label='Причина отсутствия', style=discord.TextStyle.paragraph)
    start_input = discord.ui.TextInput(label='Со скольки (Время МСК)', style=discord.TextStyle.short,
                                       placeholder='14:00', max_length=5)
    end_input = discord.ui.TextInput(label='До скольки (Время МСК)', style=discord.TextStyle.short, placeholder='20:00',
                                     max_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        DB.execute(
            'INSERT INTO afk_requests (user_id, reason, start_time, end_time) VALUES (?, ?, ?, ?)',
            (interaction.user.id, self.reason_input.value, self.start_input.value, self.end_input.value)
        )
        await interaction.response.send_message("✅ Ваша заявка на АФК отправлена на рассмотрение!", ephemeral=True)


class NVSRemovalModal(discord.ui.Modal, title='Анкета на снятие НВС'):
    index_input = discord.ui.TextInput(label='Какой по счету НВС? (1, 2 или 3)', style=discord.TextStyle.short,
                                       max_length=1)
    comment_input = discord.ui.TextInput(label='Комментарий / Отработка', style=discord.TextStyle.paragraph)
    image_input = discord.ui.TextInput(label='Ссылка на док-ва отработки', style=discord.TextStyle.short,
                                       placeholder='Вставьте ссылку здесь')

    async def on_submit(self, interaction: discord.Interaction):
        nvs_count = get_nvs_count(interaction.user.id)
        if nvs_count == 0:
            return await interaction.response.send_message("❌ У вас нет активных НВС для снятия!", ephemeral=True)

        DB.execute(
            'INSERT INTO nvs_removals (user_id, nvs_index, comment, image_url) VALUES (?, ?, ?, ?)',
            (interaction.user.id, self.index_input.value, self.comment_input.value, self.image_input.value)
        )
        await interaction.response.send_message("✅ Заявка на снятие НВС отправлена!", ephemeral=True)


class InfoMenuView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="📚 Знания", style=discord.ButtonStyle.secondary, row=0)
    async def btn_knowledge(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_stub(interaction, "Обязательные знания", ReturnToInfoView(self.user_id))

    @discord.ui.button(label="💡 Полезное", style=discord.ButtonStyle.secondary, row=0)
    async def btn_useful(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_stub(interaction, "Полезная информация", ReturnToInfoView(self.user_id))

    @discord.ui.button(label="📰 Новости", style=discord.ButtonStyle.secondary, row=0)
    async def btn_news(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_stub(interaction, "Новости", ReturnToInfoView(self.user_id))

    @discord.ui.button(label="🌐 Онлайн", style=discord.ButtonStyle.secondary, row=1)
    async def btn_online(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_stub(interaction, "Онлайн серверов", ReturnToInfoView(self.user_id))

    @discord.ui.button(label="🕒 Расписание", style=discord.ButtonStyle.secondary, row=1)
    async def btn_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_stub(interaction, "Расписание", ReturnToInfoView(self.user_id))

    @discord.ui.button(label="📈 Повышение", style=discord.ButtonStyle.secondary, row=1)
    async def btn_promo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_stub(interaction, "Система повышения", ReturnToInfoView(self.user_id))

    @discord.ui.button(label="🔙 Назад в меню", style=discord.ButtonStyle.danger, row=2)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_main_menu_embed(), view=MainMenuView(self.user_id))


class NVSMenuView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="📋 Мои НВС", style=discord.ButtonStyle.primary, row=0)
    async def my_nvs_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        records = DB.fetchall('SELECT reason, date FROM nvs_records WHERE user_id = ?', (interaction.user.id,))
        embed = discord.Embed(title="Ваши активные НВС", color=discord.Color.red())
        if not records:
            embed.description = "У вас нет активных наказаний! 🎉"
        else:
            for i, (reason, date) in enumerate(records, 1):
                embed.add_field(name=f"НВС #{i} | {date}", value=f"> {reason}", inline=False)
        await interaction.response.edit_message(embed=embed, view=ReturnToMainView(self.user_id))

    @discord.ui.button(label="🗑️ Заявка на снятие", style=discord.ButtonStyle.success, row=0)
    async def remove_nvs_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NVSRemovalModal())

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.danger, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_main_menu_embed(), view=MainMenuView(self.user_id))


class CreateEventModal(discord.ui.Modal, title="Создание мероприятия"):
    title_input = discord.ui.TextInput(label="Название МП", style=discord.TextStyle.short)
    time_input = discord.ui.TextInput(label="Время начала (МСК)", style=discord.TextStyle.short,
                                      placeholder="Например: 18:00")
    comment_input = discord.ui.TextInput(label="Комментарий", style=discord.TextStyle.paragraph, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        DB.execute('INSERT INTO events (title, start_time, comment, created_timestamp) VALUES (?, ?, ?, ?)',
                   (self.title_input.value, self.time_input.value, self.comment_input.value, time.time()))
        await interaction.response.send_message("✅ Мероприятие успешно создано и будет удалено через 2.5 часа!",
                                                ephemeral=True)


class IssueNVSModal(discord.ui.Modal, title='Выдача НВС'):
    static_input = discord.ui.TextInput(label='Статик нарушителя', style=discord.TextStyle.short)
    reason_input = discord.ui.TextInput(label='Причина НВС', style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        user = DB.fetchone('SELECT user_id, character_name FROM users WHERE majestic_static = ?',
                           (int(self.static_input.value),))
        if not user:
            return await interaction.response.send_message("❌ Игрок не найден в базе!", ephemeral=True)

        DB.execute('INSERT INTO nvs_records (user_id, reason, date) VALUES (?, ?, ?)',
                   (user[0], self.reason_input.value, datetime.now().strftime("%d.%m.%Y")))
        await interaction.response.send_message(f"✅ Игроку **{user[1]}** ({self.static_input.value}) выдан НВС.",
                                                ephemeral=True)
        await notify_user(interaction, user[0],
                          f"⚠️ **Уведомление о наказании**\nВам был выдан НВС.\n**Причина:** {self.reason_input.value}")


class RankSelectView(discord.ui.View):
    def __init__(self, target_user_id: int, current_rank: str):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

        options = [discord.SelectOption(label=r, default=(r == current_rank)) for r in RANKS]
        self.select = discord.ui.Select(placeholder="Выберите новый ранг", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        new_rank = self.select.values[0]
        DB.execute('UPDATE users SET rank = ? WHERE user_id = ?', (new_rank, self.target_user_id))
        embed = discord.Embed(title="✅ Успех", description=f"Ранг пользователя успешно изменен на **{new_rank}**!",
                              color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=ReturnToAdminView())


class RankStaticModal(discord.ui.Modal, title="Изменение ранга"):
    static_input = discord.ui.TextInput(label="Статик игрока", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        user = DB.fetchone('SELECT user_id, character_name, rank FROM users WHERE majestic_static = ?',
                           (int(self.static_input.value),))
        if not user:
            return await interaction.response.send_message("❌ Игрок не найден!", ephemeral=True)
        embed = discord.Embed(title="Управление рангом",
                              description=f"Игрок: **{user[1]}**\nТекущий ранг: **{user[2]}**", color=CUPSIZE_COLOR)
        await interaction.response.edit_message(embed=embed, view=RankSelectView(user[0], user[2]))


class AdminReviewerView(discord.ui.View):
    def __init__(self, table: str, label: str):
        super().__init__(timeout=None)
        self.table = table
        self.label = label

    async def load_next(self, interaction: discord.Interaction):
        pending_count = DB.fetchone(f'SELECT COUNT(*) FROM {self.table} WHERE status = "pending"')[0]
        record = DB.fetchone(f'SELECT * FROM {self.table} WHERE status = "pending" LIMIT 1')

        if not record:
            embed = discord.Embed(title=f"Проверка: {self.label}", description="✅ Очередь пуста! Все заявки проверены.",
                                  color=discord.Color.green())
            return await interaction.response.edit_message(embed=embed, view=ReturnToAdminView())

        self.current_req_id = record[0]
        self.target_user_id = record[1]

        user_data = DB.fetchone('SELECT character_name, majestic_static FROM users WHERE user_id = ?',
                                (self.target_user_id,))
        user_info = f"{user_data[0]} ({user_data[1]})" if user_data else f"ID: {self.target_user_id}"

        embed = discord.Embed(title=f"Рассмотрение: {self.label}",
                              description=f"⏳ В очереди осталось: **{pending_count}** шт.", color=discord.Color.gold())
        embed.add_field(name="👤 Отправитель", value=f"<@{self.target_user_id}> | {user_info}", inline=False)

        if self.table == 'afk_requests':
            embed.add_field(name="🕒 Время (МСК)", value=f"С **{record[3]}** до **{record[4]}**", inline=False)
            embed.add_field(name="📝 Причина", value=record[2], inline=False)
        elif self.table == 'reports':
            embed.add_field(name="📅 Мероприятие / Дата", value=f"**{record[2]}** | {record[3]}", inline=False)
            embed.add_field(name="💬 Комментарий", value=record[4] or "Нет", inline=False)
            embed.add_field(name="📎 Доказательства", value=f"[🔗 Открыть ссылку]({record[5]})", inline=False)
        elif self.table == 'nvs_removals':
            embed.add_field(name="❌ Снятие НВС №", value=record[2], inline=False)
            embed.add_field(name="💬 Комментарий", value=record[3], inline=False)
            embed.add_field(name="📎 Доказательства", value=f"[🔗 Открыть ссылку]({record[4]})", inline=False)

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.success)
    async def btn_approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        DB.execute(f'UPDATE {self.table} SET status = "approved" WHERE id = ?', (self.current_req_id,))
        if self.table == 'reports':
            DB.execute('UPDATE users SET reports_count = reports_count + 1 WHERE user_id = ?', (self.target_user_id,))
            msg = "✅ Ваш фото-отчет был проверен и одобрен. (+1 к статистике)"
        elif self.table == 'nvs_removals':
            nvs_id = DB.fetchone('SELECT id FROM nvs_records WHERE user_id = ? ORDER BY id ASC LIMIT 1',
                                 (self.target_user_id,))
            if nvs_id: DB.execute('DELETE FROM nvs_records WHERE id = ?', (nvs_id[0],))
            msg = "✅ Ваша заявка на снятие НВС одобрена. Наказание снято."
        else:
            msg = "✅ Ваша заявка на АФК была одобрена!"
        await notify_user(interaction, self.target_user_id, msg)
        await self.load_next(interaction)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger)
    async def btn_reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        DB.execute(f'UPDATE {self.table} SET status = "rejected" WHERE id = ?', (self.current_req_id,))
        await notify_user(interaction, self.target_user_id, f"❌ Ваша заявка ({self.label}) отклонена руководством.")
        await self.load_next(interaction)

    @discord.ui.button(label="🔙 Назад", style=discord.ButtonStyle.secondary)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="🛡️ Админ Панель", description="Выберите раздел.",
                                color=discord.Color.dark_red()), view=AdminPanelView())


class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="👥 Состав семьи", style=discord.ButtonStyle.primary, row=0)
    async def members_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        users = DB.fetchall('SELECT majestic_static, character_name, rank FROM users')
        grouped = {r: [] for r in RANKS}
        for static, name, rank in users:
            if rank in grouped:
                grouped[rank].append(f"`{static}` | {name}")

        embed = discord.Embed(title="📊 Состав семьи Cupsize", color=discord.Color.blue(),
                              description=f"Всего участников: **{len(users)}**")
        for rank in reversed(RANKS):
            if grouped[rank]:
                chunk = ""
                part = 1
                for member in grouped[rank]:
                    if len(chunk) + len(member) + 5 > 1024:
                        embed.add_field(name=f"🏆 {rank} (Часть {part})", value=chunk, inline=False)
                        chunk = ""
                        part += 1
                    chunk += member + "\n"
                if chunk:
                    embed.add_field(name=f"🏆 {rank}" if part == 1 else f"🏆 {rank} (Часть {part})", value=chunk,
                                    inline=False)

        if not users: embed.description = "База данных пуста."
        await interaction.response.edit_message(embed=embed, view=ReturnToAdminView())

    @discord.ui.button(label="⚠️ Выдать НВС", style=discord.ButtonStyle.danger, row=0)
    async def give_nvs_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(IssueNVSModal())

    @discord.ui.button(label="⬆️ Изменить ранг", style=discord.ButtonStyle.primary, row=0)
    async def rank_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RankStaticModal())

    @discord.ui.button(label="📥 Проверка Отчетов", style=discord.ButtonStyle.secondary, row=1)
    async def rev_reports_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await AdminReviewerView('reports', 'Отчеты').load_next(interaction)

    @discord.ui.button(label="📥 Проверка АФК", style=discord.ButtonStyle.secondary, row=1)
    async def rev_afk_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await AdminReviewerView('afk_requests', 'Заявки на АФК').load_next(interaction)

    @discord.ui.button(label="📥 Снятие НВС", style=discord.ButtonStyle.secondary, row=1)
    async def rev_nvs_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await AdminReviewerView('nvs_removals', 'Заявки снятия НВС').load_next(interaction)

    @discord.ui.button(label="📅 Создать МП", style=discord.ButtonStyle.success, row=2)
    async def create_event_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateEventModal())


class MainMenuView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="📱 Профиль", style=discord.ButtonStyle.primary, row=0)
    async def profile_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_data = DB.fetchone(
            'SELECT majestic_static, character_name, gender, rank, reports_count FROM users WHERE user_id = ?',
            (interaction.user.id,))
        embed = discord.Embed(title=f"Личное дело: {interaction.user.display_name}", color=CUPSIZE_COLOR)
        embed.add_field(name="👤 Игрок", value=f"> **{user_data[1]}**", inline=True)
        embed.add_field(name="🆔 Статик", value=f"> **{user_data[0]}**", inline=True)
        embed.add_field(name="🚻 Пол", value=f"> **{user_data[2]}**", inline=True)
        embed.add_field(name="🎖️ Ранг", value=f"> **{user_data[3]}**", inline=False)
        embed.add_field(name="📸 Одобрено отчетов", value=f"> **{user_data[4]} шт.**", inline=False)
        embed.add_field(name="❌ Активных НВС", value=f"> **{get_nvs_count(interaction.user.id)} шт.**", inline=False)
        embed.set_footer(text="Cupsize Family • Закрытая база данных")
        if interaction.user.avatar: embed.set_thumbnail(url=interaction.user.avatar.url)
        await interaction.response.edit_message(embed=embed, view=ReturnToMainView(self.user_id))

    @discord.ui.button(label="📸 Сдать отчет", style=discord.ButtonStyle.success, row=0)
    async def report_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal())

    @discord.ui.button(label="📅 Запись на МП", style=discord.ButtonStyle.secondary, row=0)
    async def event_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        DB.execute('DELETE FROM events WHERE created_timestamp < ?', (time.time() - 9000,))
        events = DB.fetchall('SELECT title, start_time, comment FROM events')

        embed = discord.Embed(title="📅 Актуальные мероприятия", color=discord.Color.blue())
        if not events:
            embed.description = "На данный момент нет запланированных мероприятий."
        else:
            for title, start, comment in events:
                val = f"**Время (МСК):** {start}"
                if comment: val += f"\n**Детали:** {comment}"
                embed.add_field(name=f"🔹 {title}", value=val, inline=False)
        await interaction.response.edit_message(embed=embed, view=ReturnToMainView(self.user_id))

    @discord.ui.button(label="ℹ️ Информация", style=discord.ButtonStyle.primary, row=1)
    async def info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="ℹ️ Информационный центр", description="База знаний семьи.", color=CUPSIZE_COLOR)
        await interaction.response.edit_message(embed=embed, view=InfoMenuView(self.user_id))

    @discord.ui.button(label="💤 Режим АФК", style=discord.ButtonStyle.secondary, row=1)
    async def afk_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AFKModal())

    @discord.ui.button(label="❌ Панель НВС", style=discord.ButtonStyle.danger, row=1)
    async def nvs_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="❌ Панель управления НВС", description="Выберите действие:",
                              color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=NVSMenuView(self.user_id))


class UnregisteredView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚙️ Пройти регистрацию", style=discord.ButtonStyle.success)
    async def reg_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal())


class CupsizeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.default())

    async def setup_hook(self) -> None:
        init_db()
        await self.tree.sync()

    async def on_ready(self) -> None:
        print(f'✅ Бот {self.user} запущен! (Stable Link Version)')


bot = CupsizeBot()


@bot.tree.command(name="меню", description="Открыть планшет семьи Cupsize (Для игроков)")
async def menu(interaction: discord.Interaction):
    if is_registered(interaction.user.id):
        await interaction.response.send_message(embed=get_main_menu_embed(), view=MainMenuView(interaction.user.id),
                                                ephemeral=True)
    else:
        embed = discord.Embed(title="🔒 Доступ закрыт", description="Необходима регистрация.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, view=UnregisteredView(), ephemeral=True)


@bot.tree.command(name="admin", description="Открыть панель управления (Только для Администрации)")
@app_commands.default_permissions(administrator=True)
async def admin_panel(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ Админ Панель", description="Выберите раздел для модерирования.",
                          color=discord.Color.dark_red())
    await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)


if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))