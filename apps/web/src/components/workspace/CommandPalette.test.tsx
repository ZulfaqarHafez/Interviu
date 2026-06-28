import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CommandPalette } from "./CommandPalette";

const pushMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock })
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("CommandPalette", () => {
  afterEach(() => {
    pushMock.mockReset();
  });

  it("opens with Ctrl-K, filters commands, and navigates on Enter", async () => {
    const user = userEvent.setup();
    renderWithClient(<CommandPalette />);

    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    const input = await screen.findByRole("textbox", { name: /command palette search/i });
    await user.type(input, "suites");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/suites"));
  });

  it("shows an empty state for unmatched filters", async () => {
    const user = userEvent.setup();
    renderWithClient(<CommandPalette />);

    fireEvent(window, new Event("assay:open-cmdk"));
    const input = await screen.findByRole("textbox", { name: /command palette search/i });
    await user.type(input, "zzzz-no-match");

    expect(screen.getByText(/no matches for/i)).toBeInTheDocument();
  });
});
