import SwiftUI

struct TeamMember: Identifiable {
    let id = UUID()
    var name: String
    var email: String
    var role: TeamRole
    var initials: String { name.split(separator: " ").compactMap(\.first).map(String.init).joined() }

    enum TeamRole: String, CaseIterable {
        case admin = "Admin"
        case manager = "Manager"
        case viewer = "Viewer"
    }
}

struct TeamView: View {
    @State private var members: [TeamMember] = TeamMember.samples
    @State private var showInviteSheet = false

    var body: some View {
        List {
            Section("\(members.count) members") {
                ForEach(members) { member in
                    HStack(spacing: 12) {
                        ZStack {
                            Circle()
                                .fill(roleColor(member.role).opacity(0.15))
                                .frame(width: 40, height: 40)
                            Text(member.initials)
                                .font(.system(size: 14, weight: .bold))
                                .foregroundColor(roleColor(member.role))
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text(member.name).font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                            Text(member.email).font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
                        }
                        Spacer()
                        RolePill(role: member.role)
                    }
                    .padding(.vertical, 4)
                }
                .onDelete { idx in members.remove(atOffsets: idx) }
            }
        }
        .navigationTitle("Team")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showInviteSheet = true
                } label: {
                    Label("Invite", systemImage: "person.badge.plus")
                        .foregroundColor(AppTheme.primary)
                }
            }
        }
        .sheet(isPresented: $showInviteSheet) {
            InviteTeamMemberSheet { member in members.append(member) }
        }
    }

    private func roleColor(_ role: TeamMember.TeamRole) -> Color {
        switch role {
        case .admin: return AppTheme.primary
        case .manager: return AppTheme.warning
        case .viewer: return AppTheme.textSecondary
        }
    }
}

struct RolePill: View {
    let role: TeamMember.TeamRole
    private var color: Color {
        switch role {
        case .admin: return AppTheme.primary
        case .manager: return AppTheme.warning
        case .viewer: return AppTheme.textSecondary
        }
    }
    var body: some View {
        Text(role.rawValue)
            .font(.system(size: 11, weight: .semibold))
            .foregroundColor(color)
            .padding(.horizontal, 8).padding(.vertical, 4)
            .background(color.opacity(0.12))
            .cornerRadius(6)
    }
}

struct InviteTeamMemberSheet: View {
    @Environment(\.dismiss) var dismiss
    let onAdd: (TeamMember) -> Void
    @State private var name = ""
    @State private var email = ""
    @State private var role: TeamMember.TeamRole = .manager

    var body: some View {
        NavigationStack {
            Form {
                Section("Member details") {
                    TextField("Full name", text: $name)
                    TextField("Email address", text: $email)
                        .keyboardType(.emailAddress).autocapitalization(.none)
                }
                Section {
                    Picker("Role", selection: $role) {
                        ForEach(TeamMember.TeamRole.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.inline)
                } header: {
                    Text("Role")
                } footer: {
                    Text("Admins can manage billing and team members. Managers can post jobs and review candidates. Viewers have read-only access.")
                }
            }
            .navigationTitle("Invite member")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Send invite") {
                        guard !name.isEmpty, !email.isEmpty else { return }
                        onAdd(TeamMember(name: name, email: email, role: role))
                        dismiss()
                    }
                    .fontWeight(.semibold).foregroundColor(AppTheme.primary)
                    .disabled(name.isEmpty || email.isEmpty)
                }
            }
        }
        .presentationDetents([.medium])
    }
}

extension TeamMember {
    static let samples: [TeamMember] = [
        TeamMember(name: "Alex Rivera", email: "alex@company.com", role: .admin),
        TeamMember(name: "Jordan Chen", email: "jordan@company.com", role: .manager),
        TeamMember(name: "Sam Patel", email: "sam@company.com", role: .manager),
        TeamMember(name: "Morgan Kim", email: "morgan@company.com", role: .viewer),
    ]
}
