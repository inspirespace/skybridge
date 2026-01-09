import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ImportResults } from "@/components/import-results";

describe("ImportResults", () => {
  it("renders needs review badges when skipped or missing registration", () => {
    render(
      <ImportResults
        imported={2}
        skipped={1}
        failed={1}
        registrationMissing={1}
      />
    );

    expect(screen.getByText("Import results")).toBeInTheDocument();
    expect(screen.getByText("Total processed")).toBeInTheDocument();
    expect(screen.getAllByText(/needs review/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Skipped: 1 · Failed: 1")).toBeInTheDocument();
  });

  it("renders OK badges when no issues", () => {
    render(
      <ImportResults
        imported={3}
        skipped={0}
        failed={0}
        registrationMissing={0}
      />
    );

    expect(screen.getAllByText("OK").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Total processed")).toBeInTheDocument();
    expect(screen.getByText("Imported flights")).toBeInTheDocument();
  });
});
