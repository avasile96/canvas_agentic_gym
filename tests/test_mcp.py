"""Integration tests for the MCP server tool functions."""

import json

import mcp_server


PROMPT = (
    "Create a Summer Sale email banner with a bold headline, "
    "a yellow CTA button that says 'Shop Now', and a product image"
)


class TestMCPTools:
    def test_reset_returns_constraints(self):
        result = json.loads(mcp_server.reset_environment(PROMPT))
        assert result["state"]["canvas"]["element_count"] == 0
        types = [r["type"] for r in result["constraints"]["required_elements"]]
        assert "text" in types
        assert "shape" in types
        assert "image" in types

    def test_execute_action_adds_element(self):
        mcp_server.reset_environment(PROMPT)
        result = json.loads(mcp_server.execute_action(
            "add_text", x=200, y=50, width=400, height=60,
            content="Summer Sale!", bold=True,
        ))
        assert result["success"] is True
        assert result["state"]["canvas"]["element_count"] == 1

    def test_get_canvas_state_reflects_changes(self):
        mcp_server.reset_environment(PROMPT)
        mcp_server.execute_action("add_text", x=100, y=100, width=200, height=50, content="Hi")
        state = json.loads(mcp_server.get_canvas_state())
        assert state["canvas"]["element_count"] == 1
        assert state["elements"][0]["content"] == "Hi"

    def test_reward_improves_with_matching_elements(self):
        mcp_server.reset_environment(PROMPT)
        r0 = json.loads(mcp_server.get_current_reward())

        mcp_server.execute_action(
            "add_text", x=200, y=50, width=400, height=60,
            content="Summer Sale!", text_color="#000000", bold=True,
        )
        mcp_server.execute_action(
            "add_shape", x=300, y=200, width=200, height=50,
            color="#FFD700", shape_kind="button", text_content="Shop Now",
        )
        mcp_server.execute_action(
            "add_image", x=250, y=300, width=300, height=200,
            alt_text="Product",
        )
        r1 = json.loads(mcp_server.get_current_reward())

        assert r1["total"] > r0["total"]
        assert r1["constraint_satisfaction"] > r0["constraint_satisfaction"]

    def test_compare_canvas_states_picks_winner(self):
        mcp_server.reset_environment(PROMPT)

        # State A: empty canvas
        state_a = mcp_server.get_canvas_state()

        # State B: canvas with matching elements
        mcp_server.execute_action(
            "add_text", x=200, y=50, width=400, height=60,
            content="Sale!", bold=True,
        )
        mcp_server.execute_action(
            "add_shape", x=300, y=200, width=200, height=50,
            color="#FFD700", shape_kind="button", text_content="Shop Now",
        )
        state_b = mcp_server.get_canvas_state()

        result = json.loads(mcp_server.compare_canvas_states(state_a, state_b))
        assert result["winner"] == "b"
        assert result["delta"]["total"] < 0  # a - b is negative

    def test_render_returns_png(self):
        mcp_server.reset_environment(PROMPT)
        mcp_server.execute_action("add_text", x=100, y=100, width=200, height=50, content="Hi")
        img = mcp_server.render_canvas()
        assert img.data[:4] == b"\x89PNG"
