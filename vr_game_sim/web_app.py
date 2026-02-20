import streamlit as st
import json
import os

# Import your actual backend engine!
from main import create_armies_from_data
from game_simulator import GameSimulator

st.set_page_config(page_title="VR Simulator", layout="wide")

st.title("🛡️ Viking Rise Battle Simulator")

col1, col2 = st.columns(2)

with col1:
    st.header("Attacker")
    # You can expand these lists later by importing your actual hero lists!
    att_primary = st.selectbox("Primary Hero", ["Yulmi", "Artur", "Ivor", "Lagertha"], key="att_p")
    att_troops = st.number_input("Troop Count", value=350000, step=1000, key="att_t")

with col2:
    st.header("Defender")
    def_primary = st.selectbox("Primary Hero", ["Freydis", "Bjorn", "Ragnar", "Greta"], key="def_p")
    def_troops = st.number_input("Troop Count", value=350000, step=1000, key="def_t")

st.divider()

if st.button("Run Simulation ⚔️", use_container_width=True):
    with st.spinner("The Vikings are fighting..."):
        try:
            # 1. Load a safe, valid template from your setups
            template_path = os.path.join("setups", "1v1", "CHECK.json")
            with open(template_path, "r") as f:
                setup_data = json.load(f)

            # 2. Inject the web inputs into the template
            setup_data[0]["count"] = att_troops
            setup_data[0]["heroes"][0]["hero_name_or_preset"] = att_primary

            setup_data[1]["count"] = def_troops
            setup_data[1]["heroes"][0]["hero_name_or_preset"] = def_primary

            # 3. Create the armies and run the simulation!
            armies = create_armies_from_data(setup_data)
            sim = GameSimulator(armies[0], armies[1], track_stats=True)

            # This generates the exact same text report you see in the console
            report_text = sim.simulate_battle()

            st.success("Simulation Complete!")

            # 4. Show the results on the webpage
            st.subheader("Battle Report")
            st.text_area("Detailed Log", report_text, height=500)

        except Exception as e:
            st.error(f"An error occurred: {e}")