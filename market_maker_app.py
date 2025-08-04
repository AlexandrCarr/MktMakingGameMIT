
import math, random, statistics
import streamlit as st
from typing import List, Tuple, Dict
from pathlib import Path

# Rerun helper 
def rerun():                            
    if hasattr(st, "experimental_rerun"): st.experimental_rerun()  
    elif hasattr(st, "rerun"):           st.rerun()                 
    else:
        st.warning("Please click your browser’s Reload button."); st.stop()

# configuration
STARTING_BUDGET = 500
ROUND_SECONDS   = 20          # shown only (no enforced timer)
CARD_MEAN       = 8           # expected value of one card (2‑14 uniform)
DICE_MEAN       = 3.5         # expected value of one die  (1‑6 uniform)

SUITS = ['♥', '♦', '♣', '♠']
DICE  = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅']

# helpers fo game
def gen_hand(mode:str, n:int=None) -> List[Dict]:
    """Return list of dicts [{'value':int,'suit':str}]  (suit='' for dice)"""
    n = n or random.randint(3,5)
    if mode == 'cards':
        return [{"value": random.randint(2,14), "suit": random.choice(SUITS)} for _ in range(n)]
    else:
        return [{"value": random.randint(1,6),  "suit": ""} for _ in range(n)]

def quote_market(
        revealed:List[Dict],
        n_total:int,
        mode:str
) -> Tuple[float,float,float]:
    """Return realistic (bid,ask, true_total).
       Maker sees revealed cards only; unseen ones valued at population mean."""
    pop_mean = CARD_MEAN if mode=='cards' else DICE_MEAN
    true_total = sum(card["value"] for card in revealed)  # revealed part

    unseen = n_total - len(revealed)
    ev_visible = true_total + unseen * pop_mean

    # mid within ±10 % of EV_visible
    mid = ev_visible * (1 + random.uniform(-0.10, 0.10))

    # spread = 2–6 % of EV_visible
    spread = ev_visible * random.uniform(0.02, 0.06)

    bid = round(mid - spread/2, 2)
    ask = round(mid + spread/2, 2)
    return bid, ask, round(ev_visible,2)   # last value only for info panel

def card_symbol(val:int, suit:str) -> Tuple[str,str]:
    rank = {11:'J',12:'Q',13:'K',14:'A'}.get(val,str(val))
    colour = '#c62828' if suit in ['♥','♦'] else '#000'
    return f"{rank}{suit}", colour

def true_total(hand:List[Dict]) -> int:
    return sum(c["value"] for c in hand)

# initialization and initial state
def reset_game():
    st.session_state.update(
        stage='mode_select', mode='cards',
        round_no=0,
        budget=STARTING_BUDGET, total_pnl=0.0,
        correct=0, guesses=0,
        # per‑round
        hand=[], revealed_idx=[],
        bid=0.0, ask=0.0, est_ev=0.0,
        order_amount=1, side=None,
    )
if 'stage' not in st.session_state:
    reset_game()

S = st.session_state   # alias

#sidebar for tracker 
show_tracker = st.sidebar.checkbox("Show running P&L", value=True)
if show_tracker:
    st.sidebar.markdown(f"### 📈 Running P&L\n**{S.total_pnl:+.2f}**")
def show_hand(hidden:bool):
    cols = st.columns(len(S.hand))
    for idx,(col,card) in enumerate(zip(cols,S.hand)):
        if hidden and idx not in S.revealed_idx:
            sym, colour = "❓","#888"
        else:
            if S.mode=='cards':
                sym, colour = card_symbol(card["value"], card["suit"])
            else:
                sym, colour = DICE[card["value"]-1], "#000"
        col.markdown(
            f"<div style='font-size:42px;text-align:center;color:{colour};'>{sym}</div>",
            unsafe_allow_html=True)

# staging
def stage_mode_select():
    st.title("🏦 Market‑Making Game")
    st.subheader("Select game mode")
    c1,c2 = st.columns(2)
    if c1.button("🃏 Cards"): S.mode='cards'; S.stage='new_round'; rerun()
    if c2.button("🎲 Dice"):  S.mode='dice';  S.stage='new_round'; rerun()
    st.markdown(" ")                               # small spacer
    banner_path = Path(__file__).parent / "meme.png"
    st.image(str(banner_path), use_column_width=True)

def stage_new_round():
    S.round_no += 1
    S.hand = gen_hand(S.mode)
    # randomly reveal 0‑2 cards
    S.revealed_idx = random.sample(range(len(S.hand)), random.randint(0,2))
    revealed_cards = [S.hand[i] for i in S.revealed_idx]
    S.bid, S.ask, S.est_ev = quote_market(revealed_cards, len(S.hand), S.mode)
    S.stage='quote'; rerun()

def stage_quote():
    st.markdown(f"### Round {S.round_no}")
    st.caption(f"Time limit per decision: {ROUND_SECONDS}s (soft)")
    show_hand(hidden=True)
    st.divider()
    st.markdown(f"**Maker quotes {S.bid} @ {S.ask}.**  _(EV≈{S.est_ev})_")

    st.markdown("##### Order amount")
    b1,b2,b3,b4 = st.columns([1,1,1,2])
    for col,size in zip((b1,b2,b3),(1,5,10)):
        if col.button(str(size),key=f"qty{size}_{S.round_no}"):
            S.order_amount=size; rerun()
    b4.write(f"**Selected:** {S.order_amount}")

    c1,c2,c3 = st.columns(3)
    if c1.button("Buy ↑", use_container_width=True):
        S.side='buy'; S.stage='reveal'; rerun()
    if c2.button("Sell ↓", use_container_width=True):
        S.side='sell'; S.stage='reveal'; rerun()
    if c3.button("Skip ⏭️", use_container_width=True):
        S.side='skip'; S.guesses+=1; S.stage='post'; rerun()

    st.markdown(f"#### Budget: {S.budget:,.0f}")

def stage_reveal():
    exec_price = S.ask if S.side=='buy' else S.bid
    action = "bought" if S.side=='buy' else "sold"
    st.markdown("### Reveal")
    show_hand(hidden=False)
    st.divider()
    st.write(f"You **{action} {S.order_amount} units at {exec_price:.2f}**.")
    st.write("Enter your **PnL** for this round (use minus sign for losses):")

    guess = st.text_input("PnL", key=f"guess_{S.round_no}")
    if st.button("Submit", key=f"submit_{S.round_no}"):
        try:
            user_pnl = float(guess)
        except ValueError:
            st.error("Please input a number."); st.stop()

        total_true = true_total(S.hand)
        actual_pnl = (total_true - exec_price)*S.order_amount if S.side=='buy' \
                     else (exec_price - total_true)*S.order_amount
        actual_pnl = round(actual_pnl,2)

        S.total_pnl += actual_pnl
        S.budget    += actual_pnl
        S.guesses   += 1
        if abs(user_pnl - actual_pnl) < 1e-2:
            S.correct += 1
            st.success(f"✅ Correct! PnL = {actual_pnl:+.2f}")
        else:
            st.error  (f"❌ Wrong. Actual PnL = {actual_pnl:+.2f}")

        S.stage='post'; rerun()

def stage_post():
    st.divider()
    n,q = st.columns(2)
    if n.button("Next round ▶️"): S.stage='new_round'; rerun()
    if q.button("Finish ❌"):     S.stage='summary';  rerun()

def stage_summary():
    st.header("🎉 Game summary")
    acc = (S.correct/S.guesses*100) if S.guesses else 0
    st.write(f"Rounds played: **{S.round_no}**")
    st.write(f"Final budget: **{S.budget:,.2f}**  (start {STARTING_BUDGET})")
    st.write(f"Total PnL: **{S.total_pnl:+.2f}**")
    st.write(f"Accuracy: **{acc:.1f}%** ({S.correct}/{S.guesses})")
    if st.button("Play again"):
        reset_game(); rerun()

#router
routes = {
    'mode_select': stage_mode_select,
    'new_round'  : stage_new_round,
    'quote'      : stage_quote,
    'reveal'     : stage_reveal,
    'post'       : stage_post,
    'summary'    : stage_summary,
}
routes[S.stage]()    

