from manim import *

# Timing follows the narration: vo1 0.5s, vo2 7.8s, vo3 11.4s, vo4 18.3s, end 22.5s
AR = "Noto Naskh Arabic"
INK, A, B, C = "#F4F1EA", "#FFB547", "#7FD1B9", "#FF8C8C"


class Pythagoras(Scene):
    def construct(self):
        self.camera.background_color = "#10223A"
        u = 0.55  # one unit of side length
        p0, p1, p2 = LEFT * 2 * u + DOWN * 1.5 * u, RIGHT * 2 * u + DOWN * 1.5 * u, LEFT * 2 * u + UP * 1.5 * u
        shift = LEFT * 2.2 + UP * 0.35
        p0, p1, p2 = p0 + shift, p1 + shift, p2 + shift

        title = Text("المثلث القائم", font=AR, color=INK, weight=BOLD).scale(0.9).to_corner(UR, buff=0.7)
        tri = Polygon(p0, p1, p2, color=INK, stroke_width=6)
        right = RightAngle(Line(p0, p1), Line(p0, p2), length=0.3, color=INK)
        la = MathTex("a", color=A).next_to(Line(p0, p2), LEFT)
        lb = MathTex("b", color=B).next_to(Line(p0, p1), DOWN)
        lc = MathTex("c", color=C).move_to((p1 + p2) / 2 + RIGHT * 0.35 + UP * 0.3)

        # 1 · the triangle (0 → 7.6 s)
        self.wait(0.3)
        self.play(FadeIn(title, shift=DOWN * 0.3), Create(tri), run_time=1.6)
        self.play(Create(right), Write(la), Write(lb), run_time=1.5)
        self.play(Write(lc), Indicate(Line(p1, p2, color=C, stroke_width=10)), run_time=1.6)
        self.wait(2.6)

        # 2 · a square on every side (7.6 → 11.2 s)
        sq_a = Polygon(p0, p2, p2 + LEFT * 3 * u, p0 + LEFT * 3 * u, color=A, fill_opacity=0.35, stroke_width=4)
        sq_b = Polygon(p0, p1, p1 + DOWN * 4 * u, p0 + DOWN * 4 * u, color=B, fill_opacity=0.35, stroke_width=4)
        n = rotate_vector(p1 - p2, PI / 2)
        if np.dot(n, p0 - p2) > 0:  # the square must sit outside the triangle
            n = -n
        sq_c = Polygon(p2, p1, p1 + n, p2 + n, color=C, fill_opacity=0.35, stroke_width=4)
        self.play(FadeOut(la, lb, lc), run_time=0.4)
        self.play(LaggedStart(DrawBorderThenFill(sq_a), DrawBorderThenFill(sq_b), DrawBorderThenFill(sq_c),
                              lag_ratio=0.35), run_time=2.6)
        self.wait(0.6)

        # 3 · areas add up (11.2 → 18.1 s)
        na = MathTex("a^2{=}9", color=A).scale(0.75).move_to(sq_a)
        nb = MathTex("b^2{=}16", color=B).scale(0.85).move_to(sq_b)
        nc = MathTex("c^2{=}25", color=C).scale(1.0).move_to(sq_c)
        self.play(Write(na), Write(nb), run_time=1.4)
        self.play(Write(nc), run_time=1.0)
        eq = MathTex("a^2", "+", "b^2", "=", "c^2").scale(1.5).to_edge(RIGHT, buff=0.9).shift(UP * 0.6)
        eq[0].set_color(A); eq[2].set_color(B); eq[4].set_color(C)
        nums = MathTex("9", "+", "16", "=", "25").scale(1.3).next_to(eq, DOWN, buff=0.5)
        nums[0].set_color(A); nums[2].set_color(B); nums[4].set_color(C)
        self.play(TransformFromCopy(VGroup(na, nb, nc), nums), run_time=1.6)
        self.play(Write(eq), run_time=1.4)
        self.wait(1.5)

        # 4 · the name (18.1 → 22.5 s)
        name = Text("نظرية فيثاغورس", font=AR, color=A, weight=BOLD).scale(0.85).next_to(nums, DOWN, buff=0.7)
        box = SurroundingRectangle(VGroup(eq, nums), color=A, buff=0.3, corner_radius=0.15)
        self.play(Write(name), Create(box), run_time=1.6)
        self.play(Circumscribe(eq, color=INK), run_time=1.4)
        self.wait(1.4)
