
import random
import time

import streamlit as st
from supabase import create_client


# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Card Guessing Game",
    page_icon="🃏",
    layout="centered"
)

st.title("🃏 Card Guessing Game")
st.write("Make four correct guesses in a row to win!")


# ==========================================
# SUPABASE CONNECTION
# ==========================================

@st.cache_resource
def get_database():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


# ==========================================
# CARD SETTINGS
# ==========================================

SUITS = ["Hearts", "Diamonds", "Clubs", "Spades"]

SYMBOLS = {
    "Hearts": "♥",
    "Diamonds": "♦",
    "Clubs": "♣",
    "Spades": "♠"
}

CARD_NAMES = {
    1: "Ace (A)",
    11: "Jack (J)",
    12: "Queen (Q)",
    13: "King (K)"
}


def card_name(value):
    return CARD_NAMES.get(value, str(value))


def create_deck():
    deck = []

    for suit in SUITS:
        for value in range(1, 14):
            deck.append({
                "value": value,
                "suit": suit,
                "color": (
                    "Red" if suit in ["Hearts", "Diamonds"]
                    else "Black"
                )
            })

    random.shuffle(deck)
    return deck


def card_text(card):
    return (
        f"{card_name(card['value'])} "
        f"of {card['suit']} "
        f"{SYMBOLS[card['suit']]}"
    )


def display_card(card):
    color = (
        "#dc2626"
        if card["color"] == "Red"
        else "#111827"
    )

    st.markdown(
        f"""
        <div style="
            display:inline-block;
            background:white;
            color:{color};
            border:2px solid #cccccc;
            border-radius:12px;
            padding:18px;
            margin:5px;
            min-width:100px;
            text-align:center;
            font-size:22px;
            font-weight:bold;
        ">
            {card_name(card["value"])}
            <br>
            {SYMBOLS[card["suit"]]}
        </div>
        """,
        unsafe_allow_html=True
    )


# ==========================================
# GAME STATE
# ==========================================

def new_game_state():
    return {
        "deck": create_deck(),
        "cards": [],
        "round": 1,
        "failed_attempts": 0,
        "started_at": None,
        "elapsed": None,
        "won": False,
        "saved": False,
        "message": "",
        "message_type": "info"
    }


if "classic_game" not in st.session_state:
    st.session_state.classic_game = new_game_state()

if "timed_game" not in st.session_state:
    st.session_state.timed_game = new_game_state()

if "player_name" not in st.session_state:
    st.session_state.player_name = ""


def reset_attempt(game):
    # Reset cards and round, but preserve
    # failed attempts and the running timer.
    game["deck"] = create_deck()
    game["cards"] = []
    game["round"] = 1


def reset_game(mode):
    st.session_state[f"{mode}_game"] = new_game_state()


# ==========================================
# DATABASE FUNCTIONS
# ==========================================

def save_score(mode, game):
    if game["saved"]:
        return True

    name = st.session_state.player_name.strip()

    if not name:
        return False

    score = {
        "player_name": name,
        "game_mode": mode,
        "failed_attempts": game["failed_attempts"],
        "completion_time": (
            round(game["elapsed"], 3)
            if mode == "timed"
            else None
        )
    }

    try:
        db = get_database()

        db.table("game_scores").insert(
            score
        ).execute()

        game["saved"] = True
        return True

    except Exception as error:
        st.error(f"Could not save score: {error}")
        return False


def load_scores(mode):
    try:
        db = get_database()

        query = (
            db.table("game_scores")
            .select(
                "player_name, failed_attempts, "
                "completion_time, created_at"
            )
            .eq("game_mode", mode)
        )

        if mode == "classic":
            query = query.order(
                "failed_attempts",
                desc=False
            )
        else:
            query = query.order(
                "completion_time",
                desc=False
            )

        response = query.limit(20).execute()
        return response.data

    except Exception as error:
        st.error(f"Could not load leaderboard: {error}")
        return []


# ==========================================
# CHECK GUESSES
# ==========================================

def make_guess(mode, guess):
    game = st.session_state[f"{mode}_game"]

    if game["won"]:
        return

    # Start timer on the first guess.
    if mode == "timed" and game["started_at"] is None:
        game["started_at"] = time.time()

    current_round = game["round"]

    # Draw a new card.
    card = game["deck"].pop()

    correct = False

    # ROUND 1: COLOR
    if current_round == 1:
        correct = guess == card["color"]

    # ROUND 2: HIGHER OR LOWER
    elif current_round == 2:
        previous = game["cards"][0]["value"]

        if guess == "Higher":
            correct = card["value"] > previous

        elif guess == "Lower":
            correct = card["value"] < previous

    # ROUND 3: INSIDE OR OUTSIDE
    elif current_round == 3:
        value1 = game["cards"][0]["value"]
        value2 = game["cards"][1]["value"]

        low = min(value1, value2)
        high = max(value1, value2)

        inside = low < card["value"] < high

        outside = (
            card["value"] < low
            or card["value"] > high
        )

        if guess == "Inside":
            correct = inside

        elif guess == "Outside":
            correct = outside

    # ROUND 4: SUIT
    elif current_round == 4:
        correct = guess == card["suit"]

    game["cards"].append(card)

    # ======================================
    # CORRECT GUESS
    # ======================================

    if correct:
        if current_round == 4:
            game["won"] = True

            if mode == "timed":
                game["elapsed"] = (
                    time.time() - game["started_at"]
                )

            game["message"] = (
                f"You won! Final card: {card_text(card)}"
            )
            game["message_type"] = "success"

        else:
            game["round"] += 1
            game["message"] = (
                f"Correct! You drew {card_text(card)}."
            )
            game["message_type"] = "success"

    # ======================================
    # INCORRECT GUESS
    # ======================================

    else:
        game["failed_attempts"] += 1

        game["message"] = (
            f"Incorrect! You drew {card_text(card)}. "
            "Starting again at Round 1."
        )
        game["message_type"] = "error"

        reset_attempt(game)


# ==========================================
# GAME INTERFACE
# ==========================================

def show_game(mode):
    game = st.session_state[f"{mode}_game"]

    if mode == "classic":
        st.header("Classic Mode")
        st.write(
            "Win with as few failed attempts as possible."
        )

    else:
        st.header("Timed Mode")
        st.write(
            "Complete all four rounds as fast as possible. "
            "The timer continues after incorrect guesses."
        )

    st.divider()

    # --------------------------------------
    # WIN SCREEN
    # --------------------------------------

    if game["won"]:
        st.success("🏆 Congratulations! You won!")

        if mode == "classic":
            st.metric(
                "Failed Attempts",
                game["failed_attempts"]
            )

        else:
            st.metric(
                "Completion Time",
                f"{game['elapsed']:.2f} seconds"
            )

            st.write(
                f"Failed attempts: "
                f"{game['failed_attempts']}"
            )

        if not game["saved"]:
            if save_score(mode, game):
                st.success("Score saved to leaderboard!")
            else:
                st.warning(
                    "Enter your player name above "
                    "to save your score."
                )

                if st.button(
                    "Save Score",
                    key=f"save_{mode}"
                ):
                    if save_score(mode, game):
                        st.rerun()
        else:
            st.info("Your score is saved.")

        if st.button(
            "Play Again",
            key=f"play_again_{mode}"
        ):
            reset_game(mode)
            st.rerun()

        return

    # --------------------------------------
    # CURRENT GAME STATUS
    # --------------------------------------

    st.progress((game["round"] - 1) / 4)

    st.write(f"**Round {game['round']} of 4**")

    if mode == "timed":
        if game["started_at"] is None:
            st.info(
                "The timer starts with your first guess."
            )
        else:
            elapsed = time.time() - game["started_at"]
            st.write(
                f"⏱️ Elapsed time: {elapsed:.1f} seconds"
            )
            st.caption(
                "Time updates when you make a guess."
            )

    # --------------------------------------
    # DISPLAY RESULT MESSAGE
    # --------------------------------------

    if game["message"]:
        if game["message_type"] == "error":
            st.error(game["message"])
        else:
            st.success(game["message"])

    # --------------------------------------
    # DISPLAY DRAWN CARDS
    # --------------------------------------

    if game["cards"]:
        st.subheader("Cards Drawn")

        columns = st.columns(4)

        for i, card in enumerate(game["cards"]):
            with columns[i]:
                display_card(card)

    st.divider()

    # --------------------------------------
    # ROUND 1
    # --------------------------------------

    if game["round"] == 1:
        st.subheader("Round 1: Red or Black")
        st.write("What color will the card be?")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "🔴 Red",
                key=f"{mode}_red",
                use_container_width=True
            ):
                make_guess(mode, "Red")
                st.rerun()

        with col2:
            if st.button(
                "⚫ Black",
                key=f"{mode}_black",
                use_container_width=True
            ):
                make_guess(mode, "Black")
                st.rerun()

    # --------------------------------------
    # ROUND 2
    # --------------------------------------

    elif game["round"] == 2:
        st.subheader("Round 2: Higher or Lower")

        st.write(
            "Will the next card be higher or lower "
            "than the previous card?"
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "⬆️ Higher",
                key=f"{mode}_higher",
                use_container_width=True
            ):
                make_guess(mode, "Higher")
                st.rerun()

        with col2:
            if st.button(
                "⬇️ Lower",
                key=f"{mode}_lower",
                use_container_width=True
            ):
                make_guess(mode, "Lower")
                st.rerun()

    # --------------------------------------
    # ROUND 3
    # --------------------------------------

    elif game["round"] == 3:
        st.subheader("Round 3: Inside or Outside")

        value1 = card_name(
            game["cards"][0]["value"]
        )
        value2 = card_name(
            game["cards"][1]["value"]
        )

        st.write(
            f"Will the next card fall between "
            f"{value1} and {value2}, or outside?"
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "Inside",
                key=f"{mode}_inside",
                use_container_width=True
            ):
                make_guess(mode, "Inside")
                st.rerun()

        with col2:
            if st.button(
                "Outside",
                key=f"{mode}_outside",
                use_container_width=True
            ):
                make_guess(mode, "Outside")
                st.rerun()

    # --------------------------------------
    # ROUND 4
    # --------------------------------------

    elif game["round"] == 4:
        st.subheader("Round 4: Guess the Suit")

        st.write(
            "What suit will the final card be?"
        )

        for suit in SUITS:
            if st.button(
                f"{SYMBOLS[suit]} {suit}",
                key=f"{mode}_{suit}",
                use_container_width=True
            ):
                make_guess(mode, suit)
                st.rerun()

    st.divider()

    if st.button(
        "Restart Game",
        key=f"restart_{mode}"
    ):
        reset_game(mode)
        st.rerun()


# ==========================================
# LEADERBOARDS
# ==========================================

def show_leaderboards():
    st.header("🏆 Leaderboards")

    st.write(
        "Compare your scores with other players."
    )

    if st.button("Refresh Leaderboards"):
        st.rerun()

    st.divider()

    # --------------------------------------
    # CLASSIC LEADERBOARD
    # --------------------------------------

    st.subheader("Classic Mode Leaderboard")

    st.caption(
        "Ranked by fewest failed attempts."
    )

    classic_scores = load_scores("classic")

    if classic_scores:
        rows = []

        for rank, score in enumerate(
            classic_scores, start=1
        ):
            rows.append({
                "Rank": rank,
                "Player": score["player_name"],
                "Failed Attempts": (
                    score["failed_attempts"]
                )
            })

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No Classic Mode scores yet.")

    st.divider()

    # --------------------------------------
    # TIMED LEADERBOARD
    # --------------------------------------

    st.subheader("Timed Mode Leaderboard")

    st.caption(
        "Ranked by fastest completion time."
    )

    timed_scores = load_scores("timed")

    if timed_scores:
        rows = []

        for rank, score in enumerate(
            timed_scores, start=1
        ):
            rows.append({
                "Rank": rank,
                "Player": score["player_name"],
                "Time (seconds)": round(
                    float(score["completion_time"]), 2
                ),
                "Failed Attempts": (
                    score["failed_attempts"]
                )
            })

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No Timed Mode scores yet.")


# ==========================================
# MAIN APP TABS
# ==========================================

st.text_input(
    "Player Name",
    key="player_name",
    max_chars=30,
    placeholder="Enter your name"
)

classic_tab, timed_tab, leaderboard_tab = st.tabs([
    "🃏 Classic",
    "⏱️ Timed",
    "🏆 Leaderboards"
])

with classic_tab:
    show_game("classic")

with timed_tab:
    show_game("timed")
with leaderboard_tab:     
    show_leaderboards()
