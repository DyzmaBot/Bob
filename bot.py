"""DyzmaBot — lekki bot Discord dla społeczności NikodemDyzmaYT.

Uruchomienie: python bot.py
Serwer powstaje DOPIERO po /dyzma_setup (wymaga Administratora).
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

from data_store import StateStore

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
try:
    GUILD_ID = int(os.getenv("GUILD_ID", "0"))
except ValueError:
    GUILD_ID = 0
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
CHANNEL_URL = "https://www.youtube.com/@NikodemDyzmaYT"
RED = discord.Colour.from_rgb(198, 38, 44)
DARK = discord.Colour.from_rgb(31, 31, 36)
MOD_ROLE = "Moderator"
VIEWER_ROLE = "Widz"
logger = logging.getLogger("dyzmabot")
store = StateStore(Path(__file__).parent / "data" / "state.json")

# Ustawienia nie niszczą ani nie kasują istniejących kanałów.
CATEGORIES = [
    ("💬 SPOŁECZNOŚĆ", "public", [
        ("chat", "text"), ("szukam-ekipy", "text"),
        ("propozycje-gier", "text"), ("klipy-i-screeny", "text"),
    ]),
    ("📌 INFORMACJE", "public", [
        ("ogloszenia", "readonly"), ("na-zywo", "readonly"),
        ("plan-streamow", "readonly"), ("powitania", "readonly"),
    ]),
    ("🎧 GŁOSOWE", "public", [
        ("pogaduchy", "voice"), ("wspolne-granie", "voice"),
    ]),
    ("🔒 EKIPA", "private", [
        ("moderacja", "text"), ("panel-administracji", "readonly"),
    ]),
    ("✅ START", "entry", [("regulamin", "readonly")]),
]


def allowed_mod(interaction: discord.Interaction) -> bool:
    user = interaction.user
    guild = interaction.guild
    if not guild or not isinstance(user, discord.Member):
        return False
    return user.id == guild.owner_id or user.guild_permissions.administrator or any(
        role.name == MOD_ROLE for role in user.roles
    )


def require_youtube_url(value: str) -> str:
    value = value.strip() or CHANNEL_URL + "/live"
    parsed = urlparse(value)
    allowed = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in allowed:
        raise ValueError("Podaj pełny adres HTTPS do YouTube (youtube.com lub youtu.be).")
    return value


def embed(title: str, description: str, color: discord.Colour = RED) -> discord.Embed:
    result = discord.Embed(title=title, description=description[:4096], color=color)
    result.set_footer(text="DYZMA • NikodemDyzmaYT")
    return result


class DyzmaClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default(), allowed_mentions=discord.AllowedMentions.none())
        self.tree = app_commands.CommandTree(self)
        self.setup_lock = asyncio.Lock()
        self.youtube_ready = False

    async def setup_hook(self):
        self.add_view(AcceptRulesView())
        self.add_view(AdminPanelView())
        if GUILD_ID:
            guild_obj = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
        if YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID and not self.youtube_watch.is_running():
            self.youtube_watch.start()

    async def on_ready(self):
        logger.info("DyzmaBot zalogowany: %s / %s", self.user, self.user.id if self.user else "?")

    def target_guild(self):
        return self.get_guild(GUILD_ID)

    def find_channel(self, name: str):
        guild = self.target_guild()
        if guild is None:
            return None
        return discord.utils.get(guild.text_channels, name=name)

    async def upsert(self, name: str, key: str, message_embed: discord.Embed, *, view=None):
        channel = self.find_channel(name)
        if channel is None:
            raise RuntimeError(f"Brak kanału #{name}. Uruchom /dyzma_setup.")
        ids = store.get("messages")
        prior_id = ids.get(key)
        if prior_id:
            try:
                msg = await channel.fetch_message(int(prior_id))
                await msg.edit(embed=message_embed, view=view)
                return msg
            except (discord.NotFound, discord.Forbidden):
                logger.warning("Nie znaleziono poprzedniej wiadomości %s — zostanie odtworzona", key)
        msg = await channel.send(embed=message_embed, view=view)
        ids[key] = msg.id
        store.set("messages", ids)
        try:
            await msg.pin(reason="Stały panel DyzmaBot")
        except discord.HTTPException:
            pass
        return msg

    async def refresh_schedule(self):
        return await self.upsert(
            "plan-streamow", "schedule",
            embed("📅 Plan streamów", store.get("schedule") + "\n\n" + CHANNEL_URL),
        )

    async def refresh_welcome(self):
        return await self.upsert(
            "powitania", "welcome", embed("👋 Witaj w ekipie Dyzmy!", store.get("welcome"))
        )

    async def initialize_guild(self, guild: discord.Guild):
        async with self.setup_lock:
            if guild.id != GUILD_ID:
                raise ValueError("Nieprawidłowy serwer Discord")
            self_member = guild.me
            if self_member is None or not (self_member.guild_permissions.manage_channels and self_member.guild_permissions.manage_roles):
                raise PermissionError("Bot potrzebuje uprawnień Zarządzanie kanałami i Zarządzanie rolami")
            viewer = discord.utils.get(guild.roles, name=VIEWER_ROLE)
            if viewer is None:
                viewer = await guild.create_role(name=VIEWER_ROLE, colour=discord.Colour.from_rgb(170, 170, 175),
                                                 reason="DyzmaBot: dostęp po akceptacji regulaminu")
            moderator = discord.utils.get(guild.roles, name=MOD_ROLE)
            if moderator is None:
                moderator = await guild.create_role(name=MOD_ROLE, colour=RED,
                                                    reason="DyzmaBot: rola moderatorów, przydzielana ręcznie")
            if viewer >= self_member.top_role:
                raise PermissionError("Rola bota musi być WYŻEJ niż rola 'Widz' w hierarchii serwera.")

            created = []
            for index, (category_name, privacy, channels) in enumerate(CATEGORIES):
                category = discord.utils.get(guild.categories, name=category_name)
                if privacy == "private":
                    overrides = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        viewer: discord.PermissionOverwrite(view_channel=False),
                        moderator: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                        self_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    }
                elif privacy == "entry":
                    overrides = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True),
                        viewer: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True),
                        self_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    }
                else:
                    overrides = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        viewer: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                        moderator: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                        self_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    }
                if category is None:
                    category = await guild.create_category(category_name, overwrites=overrides,
                                                           reason="DyzmaBot: instalacja serwera streamera")
                    created.append(category_name)
                else:
                    # Aktualizujemy krytyczne zabezpieczenia kategorii, bez kasowania pozostałych.
                    for target, overwrite in overrides.items():
                        await category.set_permissions(target, overwrite=overwrite, reason="DyzmaBot: uporządkowanie dostępu")
                try:
                    await category.edit(position=index, reason="DyzmaBot: kolejność kategorii")
                except discord.HTTPException:
                    logger.warning("Nie można przesunąć kategorii %s", category_name)
                for channel_name, kind in channels:
                    existing = discord.utils.get(category.channels, name=channel_name)
                    if existing is None:
                        if kind == "voice":
                            existing = await guild.create_voice_channel(channel_name, category=category,
                                                                       user_limit=5 if channel_name == "wspolne-granie" else 0)
                        else:
                            existing = await guild.create_text_channel(channel_name, category=category)
                        created.append(f"#{channel_name}")
                    if kind == "readonly" and isinstance(existing, discord.TextChannel):
                        # Jedynie Widz/@everyone nie mogą pisać; moderatorzy z zachowanymi prawami.
                        await existing.set_permissions(guild.default_role, send_messages=False)
                        await existing.set_permissions(viewer, send_messages=False)
                        await existing.set_permissions(moderator, send_messages=(privacy == "private"))
                        await existing.set_permissions(self_member, view_channel=True, send_messages=True,
                                                       read_message_history=True)

            await self.upsert("regulamin", "rules", embed(
                "📜 Regulamin społeczności DYZMA",
                "**1.** Szanuj innych — bez obrażania, gróźb i dyskryminacji.\n"
                "**2.** Nie spamuj, nie reklamuj i nie wysyłaj podejrzanych linków.\n"
                "**3.** Unikaj spoilerów bez ostrzeżenia.\n"
                "**4.** Zachowuj kulturę na czacie i kanałach głosowych.\n"
                "**5.** Przestrzegaj zasad Discorda i poleceń moderacji.\n\n"
                "Aby wejść na serwer, naciśnij **Akceptuję regulamin**."
            ), view=AcceptRulesView())
            await self.upsert("ogloszenia", "announce_header", embed(
                "📢 Ogłoszenia NikodemDyzmaYT",
                "Tutaj zobaczysz najważniejsze wiadomości dotyczące kanału, streamów i serwera."
            ))
            await self.upsert("na-zywo", "live_header", embed(
                "🔴 Transmisje YouTube", f"Powiadomienia o transmisjach znajdziesz tutaj.\n\n**Kanał YouTube:** {CHANNEL_URL}"
            ))
            await self.refresh_schedule()
            await self.refresh_welcome()
            await self.upsert("chat", "chat_intro", embed(
                "💬 Czat społeczności",
                "To główne miejsce rozmów! Porozmawiaj o grach, streamach i poznaj innych widzów."
            ))
            await self.upsert("szukam-ekipy", "lfg_intro", embed(
                "🎮 Szukam ekipy", "Napisz, w co grasz, na jakiej platformie i ile osób szukasz. Bez zbędnych formularzy."
            ))
            await self.upsert("propozycje-gier", "game_intro", embed(
                "🕹️ Propozycje gier", "Masz pomysł na grę na kolejną transmisję? Zostaw propozycję tutaj."
            ))
            await self.upsert("klipy-i-screeny", "clips_intro", embed(
                "📸 Klipy i screeny", "Najlepsze momenty z rozgrywek, zrzuty ekranu i klipy z transmisji."
            ))
            await self.upsert("panel-administracji", "admin_panel", embed(
                "🛠️ Panel DyzmaBota",
                "Przyciski poniżej są dostępne tylko dla administracji i moderatorów.\n"
                "Możesz edytować plan, opublikować ogłoszenie, zgłosić start streama i zmienić powitanie."
            ), view=AdminPanelView())
            logger.info("Zainstalowano DyzmaBot: %d utworzonych elementów", len(created))
            return created

    @tasks.loop(minutes=20)
    async def youtube_watch(self):
        if not YOUTUBE_API_KEY or not YOUTUBE_CHANNEL_ID:
            return
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {"part": "snippet", "channelId": YOUTUBE_CHANNEL_ID, "eventType": "live", "type": "video",
                  "maxResults": 1, "key": YOUTUBE_API_KEY}
        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.warning("YouTube API status=%d", response.status)
                        return
                    data = await response.json()
            items = data.get("items", [])
            if not items:
                return
            video_id = items[0].get("id", {}).get("videoId", "")
            if not video_id or video_id == store.get("last_youtube_live_id"):
                return
            channel = self.find_channel("na-zywo")
            if channel is None:
                return
            title = items[0].get("snippet", {}).get("title", "NikodemDyzmaYT — na żywo!")
            live_url = f"https://www.youtube.com/watch?v={video_id}"
            await channel.send(embed=embed("🔴 DYZMA JEST NA ŻYWO!", f"**{title[:220]}**\n\n{live_url}"))
            store.set("last_youtube_live_id", video_id)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
            logger.exception("Nie udało się sprawdzić YouTube LIVE")

    @youtube_watch.before_loop
    async def youtube_wait_for_ready(self):
        await self.wait_until_ready()


client = DyzmaClient()


class AcceptRulesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Akceptuję regulamin", style=discord.ButtonStyle.success,
                       emoji="✅", custom_id="dyzmabot:v1:accept")
    async def accept(self, interaction: discord.Interaction, _button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        if guild is None or not isinstance(member, discord.Member):
            return await interaction.response.send_message("To działa tylko na serwerze.", ephemeral=True)
        role = discord.utils.get(guild.roles, name=VIEWER_ROLE)
        if not role:
            return await interaction.response.send_message("Rola 'Widz' jeszcze nie istnieje. Powiadom administratora.", ephemeral=True)
        if role in member.roles:
            channel = client.find_channel("chat")
            return await interaction.response.send_message(
                f"Już masz dostęp! {channel.mention if channel else 'Wejdź na #chat.'}", ephemeral=True)
        try:
            await member.add_roles(role, reason="Akceptacja regulaminu DYZMA")
        except discord.Forbidden:
            return await interaction.response.send_message("Nie mogę nadać roli. Administrator musi przesunąć rolę bota wyżej.", ephemeral=True)
        channel = client.find_channel("chat")
        await interaction.response.send_message(
            f"✅ Gotowe, witaj w ekipie Dyzmy! Zacznij tutaj: {channel.mention if channel else '#chat'}", ephemeral=True)


class ModOnlyView(discord.ui.View):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not allowed_mod(interaction):
            await interaction.response.send_message("⛔ Ten panel jest tylko dla moderatorów.", ephemeral=True)
            return False
        return True


class ScheduleModal(discord.ui.Modal, title="📅 Zmień plan streamów"):
    schedule = discord.ui.TextInput(label="Plan streamów / godziny", style=discord.TextStyle.paragraph,
                                    placeholder="Np. Wtorek 18:00, Piątek 19:00", max_length=1300)

    def __init__(self):
        super().__init__()
        self.schedule.default = store.get("schedule")[:1300]

    async def on_submit(self, interaction: discord.Interaction):
        if not allowed_mod(interaction):
            return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
        store.set("schedule", str(self.schedule.value).strip())
        await client.refresh_schedule()
        await interaction.response.send_message("✅ Plan streamów zaktualizowany.", ephemeral=True)


class WelcomeModal(discord.ui.Modal, title="👋 Zmień wiadomość powitalną"):
    welcome = discord.ui.TextInput(label="Treść powitania", style=discord.TextStyle.paragraph,
                                   max_length=1300)

    def __init__(self):
        super().__init__()
        self.welcome.default = store.get("welcome")[:1300]

    async def on_submit(self, interaction: discord.Interaction):
        if not allowed_mod(interaction):
            return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
        store.set("welcome", str(self.welcome.value).strip())
        await client.refresh_welcome()
        await interaction.response.send_message("✅ Powitanie zaktualizowane.", ephemeral=True)


class AnnouncementModal(discord.ui.Modal, title="📣 Nowe ogłoszenie"):
    heading = discord.ui.TextInput(label="Tytuł", placeholder="Np. Zmiana planu", max_length=120)
    message = discord.ui.TextInput(label="Treść ogłoszenia", style=discord.TextStyle.paragraph, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        if not allowed_mod(interaction):
            return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
        channel = client.find_channel("ogloszenia")
        if channel is None:
            return await interaction.response.send_message("Najpierw użyj /dyzma_setup.", ephemeral=True)
        await channel.send(embed=embed(f"📢 {self.heading.value}", str(self.message.value)))
        await interaction.response.send_message("✅ Ogłoszenie opublikowane.", ephemeral=True)


class LiveModal(discord.ui.Modal, title="🔴 Ogłoś start streama"):
    heading = discord.ui.TextInput(label="Tytuł streama", default="NikodemDyzmaYT jest na żywo!", max_length=130)
    link = discord.ui.TextInput(label="Link do transmisji (opcjonalny)", required=False,
                                placeholder="https://www.youtube.com/watch?v=...", max_length=250)

    async def on_submit(self, interaction: discord.Interaction):
        if not allowed_mod(interaction):
            return await interaction.response.send_message("Brak uprawnień.", ephemeral=True)
        try:
            link = require_youtube_url(str(self.link.value))
        except ValueError as exc:
            return await interaction.response.send_message(str(exc), ephemeral=True)
        channel = client.find_channel("na-zywo")
        if channel is None:
            return await interaction.response.send_message("Najpierw użyj /dyzma_setup.", ephemeral=True)
        if link == store.get("last_manual_live_url"):
            # Pozwalamy publikować link /live ponownie podczas kolejnego streama.
            if link != CHANNEL_URL + "/live":
                return await interaction.response.send_message("Ten link był już ogłoszony. Zmień go, jeśli to nowy stream.", ephemeral=True)
        await channel.send(embed=embed("🔴 DYZMA JEST NA ŻYWO!", f"**{self.heading.value}**\n\n{link}"))
        store.set("last_manual_live_url", link)
        await interaction.response.send_message("✅ Ogłoszenie streama wysłane.", ephemeral=True)


class AdminPanelView(ModOnlyView):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zmień plan", emoji="📅", style=discord.ButtonStyle.primary,
                       custom_id="dyzmabot:v1:schedule")
    async def schedule_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ScheduleModal())

    @discord.ui.button(label="Ogłoszenie", emoji="📣", style=discord.ButtonStyle.primary,
                       custom_id="dyzmabot:v1:announcement")
    async def announcement_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AnnouncementModal())

    @discord.ui.button(label="Jestem na żywo", emoji="🔴", style=discord.ButtonStyle.success,
                       custom_id="dyzmabot:v1:live")
    async def live_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LiveModal())

    @discord.ui.button(label="Edytuj powitanie", emoji="👋", style=discord.ButtonStyle.secondary,
                       custom_id="dyzmabot:v1:welcome")
    async def welcome_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WelcomeModal())


class SetupConfirmView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=90)
        self.user_id = user_id

    @discord.ui.button(label="Tak, utwórz serwer DYZMA", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id or not allowed_mod(interaction):
            return await interaction.response.send_message("Tylko osoba rozpoczynająca instalację może to potwierdzić.", ephemeral=True)
        button.disabled = True
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            created = await client.initialize_guild(interaction.guild)
        except (discord.HTTPException, RuntimeError, PermissionError, ValueError) as error:
            logger.exception("Błąd konfiguracji")
            await interaction.followup.send(f"❌ Instalacja przerwana: {error}", ephemeral=True)
            return
        names = ", ".join(created[:12]) if created else "bez nowych kanałów — odświeżono panele"
        await interaction.followup.send(
            "✅ **DyzmaBot gotowy!**\n"
            f"Nowe elementy: {names}\n"
            "Nadaj zaufanym osobom rolę **Moderator** ręcznie.\n"
            "Sprawdź dostęp zwykłego widza przed zaproszeniem społeczności.", ephemeral=True)


@client.tree.command(name="dyzma_setup", description="Stwórz kanały, role i panele NikodemDyzmaYT (tylko właściciel/admin)")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def dyzma_setup(interaction: discord.Interaction):
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("To działa tylko na serwerze.", ephemeral=True)
    if interaction.guild.id != GUILD_ID:
        return await interaction.response.send_message("Nieprawidłowe ID serwera w konfiguracji.", ephemeral=True)
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Tylko właściciel lub administrator może instalować serwer.", ephemeral=True)
    await interaction.response.send_message(
        "**Przygotować DYZMA?**\n"
        "Utworzę brakujące role i 13 kanałów w 5 kategoriach, dodam regulamin, powitanie i prywatny panel. "
        "Nie usunę istniejących kanałów, ale mogę zmienić uprawnienia kategorii o identycznych nazwach.\n\n"
        "Kontynuować?", view=SetupConfirmView(interaction.user.id), ephemeral=True)


@client.tree.command(name="dyzma_status", description="Sprawdź podstawowe ustawienia DyzmaBota")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def dyzma_status(interaction: discord.Interaction):
    if not allowed_mod(interaction):
        return await interaction.response.send_message("Tylko administracja.", ephemeral=True)
    current = client.target_guild()
    await interaction.response.send_message(
        f"**DyzmaBot** — {current.name if current else 'serwer niewidoczny'}\n"
        f"✅ Bot online | Plan: {'ustawiony' if store.get('schedule') else 'brak'}\n"
        f"🔴 Auto YouTube LIVE: {'aktywne' if YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID else 'wyłączone (przycisk działa)'}\n"
        f"📁 Główny czat: {'znaleziony' if client.find_channel('chat') else 'brak — użyj /dyzma_setup'}",
        ephemeral=True)


async def main():
    if not TOKEN or TOKEN == "WPISZ_TUTAJ_TOKEN" or not GUILD_ID:
        raise SystemExit("Uzupełnij DISCORD_TOKEN oraz GUILD_ID w .env (patrz README).")
    async with client:
        await client.start(TOKEN)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
