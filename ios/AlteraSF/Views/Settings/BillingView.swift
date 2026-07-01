import SwiftUI

struct BillingView: View {
    @State private var showUpgradeSheet = false

    // Hardcoded plan data — replace with API when billing endpoint exists
    let plan = BillingPlan.pro
    let usageJobs = 12
    let usageJobLimit = 25
    let usageCandidates = 348
    let nextBillingDate = Calendar.current.date(byAdding: .month, value: 1, to: Date()) ?? Date()

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                planCard
                usageCard
                paymentCard
                invoicesCard
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 16)
            .padding(.bottom, 32)
        }
        .background(AppTheme.groupedBackground.ignoresSafeArea())
        .navigationTitle("Billing & Plans")
        .navigationBarTitleDisplayMode(.large)
        .sheet(isPresented: $showUpgradeSheet) { UpgradeSheet() }
    }

    // MARK: – Plan card

    private var planCard: some View {
        VStack(spacing: 0) {
            LinearGradient(
                colors: [AppTheme.primary, AppTheme.primaryDark],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
            .frame(height: 6)
            .cornerRadius(AppTheme.cardCornerRadius, corners: [.topLeft, .topRight])

            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 6) {
                            Image(systemName: "bolt.fill")
                                .font(.system(size: 12))
                                .foregroundColor(AppTheme.primary)
                            Text(plan.badge)
                                .font(.system(size: 11, weight: .bold))
                                .foregroundColor(AppTheme.primary)
                                .textCase(.uppercase)
                        }
                        .padding(.horizontal, 8).padding(.vertical, 4)
                        .background(AppTheme.primaryLight).cornerRadius(6)

                        Text(plan.name)
                            .font(.system(size: 24, weight: .bold))
                            .foregroundColor(AppTheme.textPrimary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(plan.price)
                            .font(.system(size: 28, weight: .bold))
                            .foregroundColor(AppTheme.textPrimary)
                        Text("/ month").font(.caption).foregroundColor(AppTheme.textSecondary)
                    }
                }

                Divider()

                HStack(spacing: 20) {
                    BillingMetric(label: "Next billing", value: nextBillingDate.formatted(.dateTime.month(.abbreviated).day().year()))
                    BillingMetric(label: "Status", value: "Active", valueColor: AppTheme.success)
                    BillingMetric(label: "Seats", value: "\(plan.seats)")
                }

                Button {
                    showUpgradeSheet = true
                } label: {
                    Text("Upgrade to Enterprise")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(AppTheme.primary)
                        .frame(maxWidth: .infinity).frame(height: 40)
                        .background(AppTheme.primaryLight)
                        .cornerRadius(AppTheme.buttonCornerRadius)
                }
            }
            .padding(16)
            .background(AppTheme.background)
            .cornerRadius(AppTheme.cardCornerRadius, corners: [.bottomLeft, .bottomRight])
        }
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }

    // MARK: – Usage card

    private var usageCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Usage this month").font(.system(size: 16, weight: .semibold))

            UsageBar(label: "Active job postings", used: usageJobs, limit: usageJobLimit, color: AppTheme.primary)
            UsageBar(label: "Candidates screened", used: usageCandidates, limit: plan.candidateLimit, color: AppTheme.success)

            HStack(spacing: 12) {
                UsageMetricBox(icon: "clock.fill", value: "\(usageCandidates / 60 + 1)h", label: "Time saved", color: AppTheme.warning)
                UsageMetricBox(icon: "diamond.fill", value: "\(Int(Double(usageCandidates) * 0.08))", label: "Diamonds found", color: AppTheme.diamond)
                UsageMetricBox(icon: "percent", value: "94", label: "Screen accuracy", color: AppTheme.success)
            }
        }
        .padding(16)
        .cardStyle()
    }

    // MARK: – Payment card

    private var paymentCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Payment method").font(.system(size: 16, weight: .semibold))
                Spacer()
                Button("Update") {}
                    .font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.primary)
            }

            HStack(spacing: 14) {
                RoundedRectangle(cornerRadius: 6)
                    .fill(Color(red: 0.1, green: 0.15, blue: 0.35))
                    .frame(width: 50, height: 32)
                    .overlay(
                        Text("VISA").font(.system(size: 12, weight: .bold)).foregroundColor(.white)
                    )
                VStack(alignment: .leading, spacing: 2) {
                    Text("Visa ending in 4242")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(AppTheme.textPrimary)
                    Text("Expires 12 / 2027")
                        .font(.caption)
                        .foregroundColor(AppTheme.textSecondary)
                }
                Spacer()
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(AppTheme.success)
            }
            .padding(12)
            .background(AppTheme.secondaryBackground)
            .cornerRadius(10)
        }
        .padding(16)
        .cardStyle()
    }

    // MARK: – Invoices

    private var invoicesCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Invoices").font(.system(size: 16, weight: .semibold))
                Spacer()
                Button("Download all") {}
                    .font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.primary)
            }

            ForEach(BillingInvoice.samples) { invoice in
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(invoice.description).font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                        Text(invoice.date).font(.caption).foregroundColor(AppTheme.textSecondary)
                    }
                    Spacer()
                    Text(invoice.amount).font(.system(size: 14, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
                    Image(systemName: "arrow.down.circle").font(.system(size: 16)).foregroundColor(AppTheme.primary).padding(.leading, 8)
                }
                .padding(.vertical, 4)
                if invoice.id != BillingInvoice.samples.last?.id { Divider() }
            }
        }
        .padding(16)
        .cardStyle()
    }
}

// MARK: – Supporting types

enum BillingPlan {
    case starter, pro, enterprise

    var name: String {
        switch self { case .starter: return "Starter"; case .pro: return "Pro"; case .enterprise: return "Enterprise" }
    }
    var badge: String {
        switch self { case .starter: return "Current Plan"; case .pro: return "Current Plan"; case .enterprise: return "Current Plan" }
    }
    var price: String {
        switch self { case .starter: return "$49"; case .pro: return "$149"; case .enterprise: return "Custom" }
    }
    var seats: Int {
        switch self { case .starter: return 3; case .pro: return 10; case .enterprise: return 0 }
    }
    var candidateLimit: Int {
        switch self { case .starter: return 200; case .pro: return 1000; case .enterprise: return 0 }
    }
}

struct BillingInvoice: Identifiable {
    let id = UUID()
    let description: String
    let date: String
    let amount: String

    static let samples = [
        BillingInvoice(description: "Pro Plan – June 2025", date: "Jun 1, 2025", amount: "$149.00"),
        BillingInvoice(description: "Pro Plan – May 2025", date: "May 1, 2025", amount: "$149.00"),
        BillingInvoice(description: "Pro Plan – Apr 2025", date: "Apr 1, 2025", amount: "$149.00"),
        BillingInvoice(description: "Pro Plan – Mar 2025", date: "Mar 1, 2025", amount: "$149.00"),
    ]
}

// MARK: – Sub-components

struct BillingMetric: View {
    let label: String; let value: String
    var valueColor: Color = AppTheme.textPrimary
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
            Text(value).font(.system(size: 13, weight: .semibold)).foregroundColor(valueColor)
        }
    }
}

struct UsageBar: View {
    let label: String; let used: Int; let limit: Int; let color: Color
    var fraction: Double { limit > 0 ? min(Double(used) / Double(limit), 1.0) : 0 }
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(label).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
                Spacer()
                Text(limit > 0 ? "\(used) / \(limit)" : "\(used)")
                    .font(.system(size: 13, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4).fill(AppTheme.secondaryBackground).frame(height: 6)
                    RoundedRectangle(cornerRadius: 4).fill(color).frame(width: geo.size.width * fraction, height: 6)
                }
            }
            .frame(height: 6)
        }
    }
}

struct UsageMetricBox: View {
    let icon: String; let value: String; let label: String; let color: Color
    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: icon).font(.system(size: 18)).foregroundColor(color)
            Text(value).font(.system(size: 16, weight: .bold)).foregroundColor(AppTheme.textPrimary)
            Text(label).font(.system(size: 10)).foregroundColor(AppTheme.textSecondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 12)
        .background(AppTheme.secondaryBackground).cornerRadius(10)
    }
}

struct UpgradeSheet: View {
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    VStack(spacing: 8) {
                        Image(systemName: "bolt.fill")
                            .font(.system(size: 40)).foregroundColor(AppTheme.primary)
                        Text("Upgrade to Enterprise")
                            .font(.title2.weight(.bold))
                        Text("Unlock unlimited jobs, candidates, and team seats with dedicated support.")
                            .font(.subheadline).foregroundColor(AppTheme.textSecondary)
                            .multilineTextAlignment(.center).padding(.horizontal, 24)
                    }
                    .padding(.top, 24)

                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(["Unlimited job postings", "Unlimited candidate screenings", "Unlimited team seats", "Custom AI question sets", "Dedicated account manager", "Priority support & SLA"], id: \.self) { feature in
                            HStack(spacing: 10) {
                                Image(systemName: "checkmark.circle.fill").foregroundColor(AppTheme.success)
                                Text(feature).font(.system(size: 14))
                            }
                        }
                    }
                    .padding(16).background(AppTheme.secondaryBackground).cornerRadius(12)
                    .padding(.horizontal, 16)

                    Button {
                        // contact sales
                    } label: {
                        Text("Contact Sales")
                            .font(.system(size: 16, weight: .semibold)).foregroundColor(.white)
                            .frame(maxWidth: .infinity).frame(height: 50)
                            .background(AppTheme.primary).cornerRadius(AppTheme.buttonCornerRadius)
                    }
                    .padding(.horizontal, 16)
                }
                .padding(.bottom, 32)
            }
            .navigationTitle("Plans").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
        }
    }
}

// Corner radius on specific corners helper
extension View {
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorner(radius: radius, corners: corners))
    }
}

struct RoundedCorner: Shape {
    var radius: CGFloat; var corners: UIRectCorner
    func path(in rect: CGRect) -> Path {
        Path(UIBezierPath(roundedRect: rect, byRoundingCorners: corners, cornerRadii: CGSize(width: radius, height: radius)).cgPath)
    }
}
