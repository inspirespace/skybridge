export type PrivacySection = {
  title: string;
  paragraphs?: string[];
  list?: string[];
};

export type PrivacyContent = {
  title: string;
  subtitle: string;
  sections: PrivacySection[];
};

export function buildPrivacyContent(retentionDays: number): PrivacyContent {
  return {
    title: "Privacy policy",
    subtitle: "This policy applies to Skybridge (Austria / EU).",
    sections: [
      {
        title: "Controller",
        paragraphs: [
          "Inspirespace e.U., Golfplatzstrasse 32/5, 4048 Puchenau, Austria, hello@inspirespace.co.",
        ],
      },
      {
        title: "Purpose of processing",
        paragraphs: [
          "Skybridge enables the import of flight data from CloudAhoy to FlySto. We process credentials only to execute the specific import requested by you and to display the review before import.",
        ],
      },
      {
        title: "Data we process (minimal by design)",
        list: [
          "Account identifiers (e.g., email address).",
          "CloudAhoy / FlySto credentials (used only for the current job; not stored).",
          "Flight data including times, routes, crew, trajectory data, and remarks.",
          "Basic technical logs (e.g., IP address, request metadata) for security and troubleshooting.",
        ],
      },
      {
        title: "Legal basis",
        list: [
          "Art. 6(1)(b) GDPR (contract performance).",
          "Art. 6(1)(f) GDPR (security and fault analysis).",
        ],
      },
      {
        title: "Hosting and processors",
        paragraphs: [
          "Production hosting is on AWS (EU). Authentication uses Amazon Cognito. For data transfer and import, CloudAhoy and FlySto are used as external services. If data is transferred outside the EU/EEA, appropriate safeguards (e.g., SCCs) are used.",
        ],
      },
      {
        title: "Retention",
        paragraphs: [
          `Import artifacts are retained for ${retentionDays} days and then automatically deleted. You can delete results earlier from the app. Access logs are kept only as long as necessary for security and diagnostics.`,
        ],
      },
      {
        title: "Your rights",
        paragraphs: [
          "You have the right of access, rectification, deletion, restriction of processing, data portability, and objection. You may also lodge a complaint with your supervisory authority.",
        ],
      },
      {
        title: "Contact",
        paragraphs: ["For privacy requests, contact hello@inspirespace.co."],
      },
    ],
  };
}
