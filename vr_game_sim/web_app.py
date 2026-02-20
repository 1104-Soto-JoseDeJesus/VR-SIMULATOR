import streamlit as st
import json

# Set up the webpage tab title and layout
st.set_page_config(page_title="VR Simulator", layout="wide")

st.title("🛡️ Viking Rise Battle Simulator")
st.write("Welcome to the web version! If you can see this, the server is working.")

# Create two columns for a neat layout
col1, col2 = st.columns(2)

with col1:
    st.header("Attacker")
    att_primary = st.selectbox("Primary Hero", ["Artur", "Ivor", "Lagertha"], key="att_p")
    att_troops = st.number_input("Troop Count", value=100000, step=1000, key="att_t")

with col2:
    st.header("Defender")
    def_primary = st.selectbox("Primary Hero", ["Bjorn", "Ragnar", "Greta"], key="def_p")
    def_troops = st.number_input("Troop Count", value=100000, step=1000, key="def_t")

st.divider()

if st.button("Run Simulation ⚔️", use_container_width=True):
    # This is a placeholder. Next we will hook this up to your game_simulator.py
    st.success(f"Simulation clicked! Ready to make {att_primary} fight {def_primary}...")