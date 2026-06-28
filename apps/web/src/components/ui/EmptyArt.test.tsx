import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentArt, ProbeArrayArt, VialArt } from "./EmptyArt";

describe("EmptyArt", () => {
  it.each([
    ["vial", VialArt],
    ["probe array", ProbeArrayArt],
    ["agent", AgentArt]
  ])("renders %s as decorative responsive svg art", (_name, Art) => {
    const { container } = render(<Art size={72} className="empty-art-test" />);
    const svg = container.querySelector("svg");

    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("width", "72");
    expect(svg).toHaveAttribute("height", "72");
    expect(svg).toHaveClass("empty-art-test");
  });
});
