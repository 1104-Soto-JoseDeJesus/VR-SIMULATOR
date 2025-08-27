from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder


def test_builder_records_and_returns_reports():
    brb = BattlefieldReportBuilder()
    brb.log_round("A", "B", {"round": 1})
    brb.log_round("A", "B", {"round": 2})
    brb.log_round("C", "D", {"round": 1})

    assert len(brb.get_engagement("A", "B")) == 2

    all_reports = brb.get_all_engagements()
    assert ("A", "B") in all_reports and ("C", "D") in all_reports
    assert len(all_reports[("C", "D")]) == 1

    brb.remove_engagement("A", "B")
    assert ("A", "B") not in brb.get_all_engagements()
