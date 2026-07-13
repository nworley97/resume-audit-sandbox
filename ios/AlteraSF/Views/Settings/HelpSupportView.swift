import SwiftUI

private struct FAQItem: Identifiable {
    let id = UUID()
    let question: String
    let answer: String
}

private let faqItems: [FAQItem] = [
    FAQItem(question: "What is AlteraSF?",
            answer: "AlteraSF is an AI-powered hiring intelligence platform that extracts claims from resumes, generates challenge questions, and scores technical relevance so you can screen faster and hire smarter."),
    FAQItem(question: "What is a Diamond candidate?",
            answer: "A Diamond is a candidate with both a high job-relevancy score and a high claim validity score — meaning their resume claims are both credible and well-aligned with the role. Diamonds are surfaced across Jobs, Candidates, and Notifications so you never miss your strongest applicants."),
    FAQItem(question: "How is the Claim Validity score calculated?",
            answer: "Claim Validity checks whether a resume statement is technically coherent, internally consistent, and aligned with the candidate's claimed role, industry, and experience level. Available on Pro and Ultra plans."),
    FAQItem(question: "Why was a candidate flagged?",
            answer: "Candidates are flagged when our anti-cheat monitoring detects they left the assessment tab more than 5 times while answering questions, which can indicate they searched for answers elsewhere."),
    FAQItem(question: "How do I add or remove team members?",
            answer: "Go to More → Team Members. Admins can invite new members by email and role, and remove members. Seat limits are enforced by your current plan — upgrade under Billing & Plans if you're at capacity."),
    FAQItem(question: "Can I change my plan from the app?",
            answer: "Yes. Open More → Billing & Plans → Change Plan to move between Starter, Pro, and Ultra. Enterprise pricing is available by contacting sales."),
]

struct HelpSupportView: View {
    var body: some View {
        List {
            Section {
                Button {
                    if let url = URL(string: "mailto:support@alterasf.com?subject=AlteraSF%20iOS%20Support") {
                        UIApplication.shared.open(url)
                    }
                } label: {
                    Label("Email support@alterasf.com", systemImage: "envelope")
                }
            } footer: {
                Text("Our team typically responds within one business day.")
            }

            Section("Frequently Asked Questions") {
                ForEach(faqItems) { item in
                    DisclosureGroup {
                        Text(item.answer)
                            .font(.system(size: 13))
                            .foregroundColor(AppTheme.textSecondary)
                            .padding(.top, 4)
                    } label: {
                        Text(item.question)
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(AppTheme.textPrimary)
                    }
                }
            }
        }
        .navigationTitle("Help & Support")
        .navigationBarTitleDisplayMode(.large)
    }
}
