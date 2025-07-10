import random
import unicodedata
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "7371994863:AAGB17gH3Ia0YzDS3GV91cYbJ_IXQHDIDTQ"

MIN_PLAYERS = 2
MAX_PLAYERS = 5

players = []
player_names = {}
hands = {}
deck = []
discard_pile = []
lobby_open = False
game_started = False
current_turn = 0

RANKS = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
SUITS_CANON = ['♠', '♥', '♦', '♣']
SUIT_VARIANTS = {
    '♠': ['♠','♠️','🖤'],
    '♥': ['♥','♥️','❤️'],
    '♦': ['♦','♦️'],
    '♣': ['♣','♣️','♧'],
}

def create_deck():
    return [r + s for s in SUITS_CANON for r in RANKS]

def normalize_card_input(raw: str) -> str:
    s = unicodedata.normalize('NFKC', raw).replace('\uFE0F','').strip().upper()
    for r in sorted(RANKS, key=len, reverse=True):
        if s.startswith(r):
            suit = s[len(r):]
            for canon, vars in SUIT_VARIANTS.items():
                if any(unicodedata.normalize('NFKC', v).upper() == suit for v in vars):
                    return r + canon
    return s

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 Правила (похоже на «Crazy Eights»):\n"
        "— Раздать 5 карт каждому\n"
        "— Первый в лобби играет /newgame\n"
        "— Игроки /join (2–5 чел.)\n"
        "— /begin — начинает партию, открывается начальная карта\n"
        "— /hand — ваши карты\n"
        "— /play <карта> — сыграть карту той же масти или ранга\n"
        "— /draw — взять карту, если нет хода (ход переходит дальше)\n"
        "— Первый, кто избавится от всех карт, выигрывает\n"
        "Используйте /newgame чтобы начать подбор игроков."
    )

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players, player_names, hands, deck, discard_pile, lobby_open, game_started, current_turn
    players.clear(); player_names.clear(); hands.clear()
    deck.clear(); discard_pile.clear()
    lobby_open = True; game_started = False; current_turn = 0
    await update.message.reply_text("🔔 Новый раунд! Игроки — /join (2–5 чел.)")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global players, player_names, lobby_open
    uid = update.effective_user.id
    if not lobby_open:
        return await update.message.reply_text("⚠ Лобби закрыто. /newgame чтобы начать.")
    if uid in players:
        return await update.message.reply_text("⚠ Вы уже в лобби.")
    if len(players) >= MAX_PLAYERS:
        return await update.message.reply_text("⚠ Лобби заполнено.")
    players.append(uid)
    player_names[uid] = update.effective_user.username or update.effective_user.first_name
    await update.message.reply_text(f"✅ {player_names[uid]} присоединился ({len(players)}/{MAX_PLAYERS})")

async def begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global lobby_open, game_started, deck, hands, discard_pile, current_turn
    if not lobby_open:
        return await update.message.reply_text("⚠ Лобби не открыт. /newgame чтобы начать.")
    if len(players) < MIN_PLAYERS:
        return await update.message.reply_text(f"⚠ Нужны минимум {MIN_PLAYERS} игрока.")
    lobby_open = False; game_started = True
    deck[:] = create_deck(); random.shuffle(deck)
    hands.update({uid: [deck.pop() for _ in range(5)] for uid in players})
    discard_pile.append(deck.pop())
    current_turn = 0
    top = discard_pile[-1]
    first = player_names[players[0]]
    await update.message.reply_text(
        f"🃏 Игра началась! Открыта карта: {top}\n"
        f"Ходит: {first}"
    )

async def hand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not game_started or uid not in hands:
        return await update.message.reply_text("⚠ Вы не участвуете или игра не началась.")
    name = player_names[uid]
    cards = ", ".join(hands[uid])
    await update.message.reply_text(f"Карты игрока {name}:\n{cards}")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_turn, game_started
    text = update.message.text or ""
    if not text.lower().startswith("/play"): return
    raw = text[len("/play"):].strip()
    if not raw:
        return await update.message.reply_text("⚠ Укажите карту: /play <карта>")
    card = normalize_card_input(raw)
    uid = update.effective_user.id
    if not game_started:
        return await update.message.reply_text("⚠ Игра ещё не началась.")
    if uid not in hands:
        return await update.message.reply_text("⚠ Вы не в игре.")
    if players[current_turn] != uid:
        nxt = player_names[players[current_turn]]
        return await update.message.reply_text(f"⚠ Сейчас ходит {nxt}.")
    top = discard_pile[-1]
    if card not in hands[uid]:
        your = ", ".join(hands[uid])
        return await update.message.reply_text(f"⚠ У вас нет «{card}». Ваши: {your}")
    # проверка ранга/масти
    if card[0:len(card)-1] != top[0:len(top)-1] and card[-1] != top[-1]:
        return await update.message.reply_text(
            f"⚠ Нельзя сыграть {card}, она не совпадает по рангу или масти с {top}."
        )
    hands[uid].remove(card)
    discard_pile.append(card)
    await update.message.reply_text(f"🃴 {player_names[uid]} сыграл {card}.")
    if not hands[uid]:
        await update.message.reply_text(f"🏆 Победил {player_names[uid]}! Игра окончена.")
        # сброс
        players.clear(); player_names.clear(); hands.clear()
        deck.clear(); discard_pile.clear()
        game_started = False
        return
    # ход переходит
    current_turn = (current_turn + 1) % len(players)
    nxt = player_names[players[current_turn]]
    await update.message.reply_text(f"Открыта карта: {discard_pile[-1]}\nХодит {nxt}.")

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_turn
    uid = update.effective_user.id
    if not game_started:
        return await update.message.reply_text("⚠ Игра ещё не началась.")
    if uid not in hands:
        return await update.message.reply_text("⚠ Вы не в игре.")
    if players[current_turn] != uid:
        nxt = player_names[players[current_turn]]
        return await update.message.reply_text(f"⚠ Сейчас ходит {nxt}.")
    if not deck:
        await update.message.reply_text("🃏 Колода пуста, пропуск хода.")
    else:
        card = deck.pop()
        hands[uid].append(card)
        await update.message.reply_text(f"🃏 Вы взяли карту: {card}")
    current_turn = (current_turn + 1) % len(players)
    nxt = player_names[players[current_turn]]
    await update.message.reply_text(f"Ходит {nxt}.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("begin", begin))
    app.add_handler(CommandHandler("hand", hand))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("draw", draw))
    app.run_polling()
print ("бот запущен")
