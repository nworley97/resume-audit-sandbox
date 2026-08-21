import Foundation

enum AppConfig {
    /// Set APIBaseURL through the target build settings or an xcconfig file.
    /// The fallback keeps local development convenient and release builds safe.
    private static var configuredBaseURL: URL? {
        guard let value = Bundle.main.object(forInfoDictionaryKey: "APIBaseURL") as? String else {
            return nil
        }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !trimmed.contains("$(") else { return nil }
        return URL(string: trimmed)
    }

    #if DEBUG
    static let baseURL = configuredBaseURL ?? URL(string: "http://localhost:5050")!
    #else
    static let baseURL = configuredBaseURL ?? URL(string: "https://app.alterasf.com")!
    #endif
}
