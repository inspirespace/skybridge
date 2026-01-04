import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SignInSection } from "@/components/app/SignInSection";
import { Accordion } from "@/components/ui/accordion";

describe("SignInSection", () => {
  it("renders CTA and calls sign-in handler", async () => {
    const onSignIn = vi.fn();
    render(
      <Accordion type="single" value="sign-in">
        <SignInSection
          allowed
          signedIn={false}
          onSignIn={onSignIn}
          actionLoading={false}
          retentionDays={7}
        />
      </Accordion>
    );

    const button = screen.getByRole("button", { name: /sign up \/ sign in/i });
    await userEvent.click(button);
    expect(onSignIn).toHaveBeenCalled();
  });

  it("disables button when signed in", () => {
    render(
      <Accordion type="single" value="sign-in">
        <SignInSection
          allowed
          signedIn
          onSignIn={() => undefined}
          actionLoading={false}
          retentionDays={7}
        />
      </Accordion>
    );
    expect(screen.getByRole("button", { name: /sign up \/ sign in/i })).toBeDisabled();
  });
});
