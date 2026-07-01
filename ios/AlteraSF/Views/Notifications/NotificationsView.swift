import SwiftUI

@MainActor
final class NotificationsViewModel: ObservableObject {
    @Published var notifications: [AppNotification] = AppNotification.samples
    var unreadCount: Int { notifications.filter { !$0.isRead }.count }

    func markAllRead() {
        for i in notifications.indices { notifications[i].isRead = true }
    }
}

struct NotificationsView: View {
    @StateObject private var vm = NotificationsViewModel()

    var body: some View {
        List {
            ForEach(vm.notifications) { notif in
                NotificationRow(notification: notif)
                    .listRowInsets(EdgeInsets())
                    .listRowSeparator(.hidden)
            }
        }
        .listStyle(.plain)
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Mark all read") {
                    withAnimation { vm.markAllRead() }
                }
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(AppTheme.primary)
                .disabled(vm.unreadCount == 0)
            }
        }
    }
}

struct NotificationRow: View {
    let notification: AppNotification

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                Circle()
                    .fill(iconBackground)
                    .frame(width: 40, height: 40)
                Image(systemName: notification.iconName)
                    .font(.system(size: 16))
                    .foregroundColor(iconColor)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(notification.title)
                    .font(.system(size: 14, weight: notification.isRead ? .regular : .semibold))
                    .foregroundColor(AppTheme.textPrimary)
                Text(notification.subtitle)
                    .font(.system(size: 13))
                    .foregroundColor(AppTheme.textSecondary)
                Text(notification.relativeTime)
                    .font(.system(size: 11))
                    .foregroundColor(AppTheme.textTertiary)
            }

            Spacer()

            if !notification.isRead {
                Circle()
                    .fill(AppTheme.primary)
                    .frame(width: 8, height: 8)
                    .padding(.top, 4)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(notification.isRead ? AppTheme.background : AppTheme.primaryLight)
        .overlay(alignment: .bottom) {
            Divider()
        }
    }

    private var iconColor: Color {
        switch notification.type {
        case .newApplication: return AppTheme.primary
        case .assessmentCompleted: return AppTheme.success
        case .diamondFound: return AppTheme.diamond
        case .draftSaved: return AppTheme.warning
        case .jobBoardViews: return Color(red: 0.4, green: 0.3, blue: 0.9)
        }
    }

    private var iconBackground: Color { iconColor.opacity(0.12) }
}
