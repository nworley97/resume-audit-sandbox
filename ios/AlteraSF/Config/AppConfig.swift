import Foundation

enum AppConfig {
    #if DEBUG
    static let baseURL = URL(string: "http://localhost:5050")!
    #else
    static let baseURL = URL(string: "https://app.alterasf.com")!
    #endif
}
