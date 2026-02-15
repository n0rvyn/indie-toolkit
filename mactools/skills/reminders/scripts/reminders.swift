#!/usr/bin/env swift

import EventKit
import Foundation

// MARK: - Configuration

let store = EKEventStore()
let dateFormatter: DateFormatter = {
    let f = DateFormatter()
    f.dateFormat = "yyyy-MM-dd HH:mm"
    f.locale = Locale(identifier: "en_US_POSIX")
    return f
}()

// MARK: - Helpers

func requestAccess() {
    let semaphore = DispatchSemaphore(value: 0)
    var granted = false

    if #available(macOS 14.0, *) {
        store.requestFullAccessToReminders { g, error in
            granted = g
            if let error = error {
                fputs("Error requesting access: \(error.localizedDescription)\n", stderr)
            }
            semaphore.signal()
        }
    } else {
        store.requestAccess(to: .reminder) { g, error in
            granted = g
            if let error = error {
                fputs("Error requesting access: \(error.localizedDescription)\n", stderr)
            }
            semaphore.signal()
        }
    }

    semaphore.wait()

    guard granted else {
        fputs("Error: Reminders access not granted. Enable in System Settings > Privacy & Security > Reminders.\n", stderr)
        exit(1)
    }
}

func fetchIncompleteReminders(in calendars: [EKCalendar]? = nil) -> [EKReminder] {
    let predicate = store.predicateForIncompleteReminders(
        withDueDateStarting: nil,
        ending: nil,
        calendars: calendars
    )
    let semaphore = DispatchSemaphore(value: 0)
    var result: [EKReminder] = []

    store.fetchReminders(matching: predicate) { reminders in
        result = reminders ?? []
        semaphore.signal()
    }

    semaphore.wait()
    return result
}

func fetchIncompleteReminders(dueDateStart: Date?, dueDateEnd: Date?, calendars: [EKCalendar]? = nil) -> [EKReminder] {
    let predicate = store.predicateForIncompleteReminders(
        withDueDateStarting: dueDateStart,
        ending: dueDateEnd,
        calendars: calendars
    )
    let semaphore = DispatchSemaphore(value: 0)
    var result: [EKReminder] = []

    store.fetchReminders(matching: predicate) { reminders in
        result = reminders ?? []
        semaphore.signal()
    }

    semaphore.wait()
    return result
}

func formatDate(_ date: Date?) -> String {
    guard let date = date else { return "-" }
    return dateFormatter.string(from: date)
}

func priorityLabel(_ priority: Int) -> String {
    switch priority {
    case 1...4: return "high"
    case 5: return "medium"
    case 6...9: return "low"
    default: return ""
    }
}

func formatReminder(_ r: EKReminder) -> String {
    let name = r.title ?? "(untitled)"
    let listName = r.calendar?.title ?? "(unknown)"
    let dueStr: String
    if let due = r.dueDateComponents, let date = Calendar.current.date(from: due) {
        dueStr = formatDate(date)
    } else {
        dueStr = "-"
    }
    let body = r.notes ?? ""
    let bodyPreview = body.isEmpty ? "-" : (body.count > 80 ? String(body.prefix(80)) + "..." : body)

    return [name, listName, dueStr, String(r.priority), bodyPreview].joined(separator: "\t")
}

func printReminders(_ reminders: [EKReminder], maxResults: Int) {
    if reminders.isEmpty {
        print("No reminders found.")
        return
    }

    let limit = min(reminders.count, maxResults)
    for i in 0..<limit {
        let r = reminders[i]
        let name = r.title ?? "(untitled)"
        let listName = r.calendar?.title ?? "(unknown)"

        let dueStr: String
        if let due = r.dueDateComponents, let date = Calendar.current.date(from: due) {
            dueStr = formatDate(date)
        } else {
            dueStr = ""
        }

        let priStr = priorityLabel(r.priority)
        let body = r.notes ?? ""
        let bodyPreview = body.isEmpty ? "" : (body.count > 80 ? String(body.prefix(80)) + "..." : body)

        print("\(i + 1). \(name)")

        var details = "   List: \(listName)"
        if !dueStr.isEmpty { details += " | Due: \(dueStr)" }
        if !priStr.isEmpty { details += " | Priority: \(priStr)" }
        print(details)

        if !bodyPreview.isEmpty {
            print("   \(bodyPreview)")
        }

        print("")
    }

    print("--- \(limit) reminder(s) shown (max \(maxResults)) ---")
}

func findCalendar(named name: String) -> EKCalendar? {
    store.calendars(for: .reminder).first { $0.title == name }
}

func parseDate(_ str: String) -> Date? {
    // Try "YYYY-MM-DD HH:MM" first
    if let d = dateFormatter.date(from: str) { return d }
    // Try "YYYY-MM-DD" (date only)
    let dateOnly = DateFormatter()
    dateOnly.dateFormat = "yyyy-MM-dd"
    dateOnly.locale = Locale(identifier: "en_US_POSIX")
    return dateOnly.date(from: str)
}

// MARK: - Commands

func cmdLists() {
    let calendars = store.calendars(for: .reminder)

    for (idx, cal) in calendars.enumerated() {
        let rems = fetchIncompleteReminders(in: [cal])
        print("\(idx + 1). \(cal.title) (\(rems.count) incomplete)")
    }
}

func cmdList(listName: String?, maxResults: Int) {
    var calendars: [EKCalendar]? = nil
    if let name = listName {
        guard let cal = findCalendar(named: name) else {
            fputs("Error: List \"\(name)\" not found.\n", stderr)
            exit(1)
        }
        calendars = [cal]
    }

    let reminders = fetchIncompleteReminders(in: calendars)
    printReminders(reminders, maxResults: maxResults)
}

func cmdToday(maxResults: Int) {
    let cal = Calendar.current
    let startOfDay = cal.startOfDay(for: Date())
    let endOfDay = cal.date(byAdding: .day, value: 1, to: startOfDay)!

    let reminders = fetchIncompleteReminders(dueDateStart: startOfDay, dueDateEnd: endOfDay)
    printReminders(reminders, maxResults: maxResults)
}

func cmdUpcoming(days: Int, maxResults: Int) {
    let cal = Calendar.current
    let startOfDay = cal.startOfDay(for: Date())
    let endDate = cal.date(byAdding: .day, value: days, to: startOfDay)!

    let reminders = fetchIncompleteReminders(dueDateStart: startOfDay, dueDateEnd: endDate)
    printReminders(reminders, maxResults: maxResults)
}

func cmdOverdue(maxResults: Int) {
    // Fetch reminders due before now
    let now = Date()
    let distantPast = Date.distantPast
    let reminders = fetchIncompleteReminders(dueDateStart: distantPast, dueDateEnd: now)
    printReminders(reminders, maxResults: maxResults)
}

func cmdSearch(keyword: String, maxResults: Int) {
    let reminders = fetchIncompleteReminders()
    let lower = keyword.lowercased()

    let matching = reminders.filter { r in
        let name = (r.title ?? "").lowercased()
        let body = (r.notes ?? "").lowercased()
        return name.contains(lower) || body.contains(lower)
    }

    printReminders(matching, maxResults: maxResults)
}

func cmdCreate(title: String, listName: String?, dueStr: String?, remindStr: String?, notes: String?, priority: Int) {
    let reminder = EKReminder(eventStore: store)
    reminder.title = title
    reminder.priority = priority

    if let name = listName {
        guard let cal = findCalendar(named: name) else {
            fputs("Error: List \"\(name)\" not found.\n", stderr)
            exit(1)
        }
        reminder.calendar = cal
    } else {
        reminder.calendar = store.defaultCalendarForNewReminders()
    }

    if let dueStr = dueStr, let date = parseDate(dueStr) {
        reminder.dueDateComponents = Calendar.current.dateComponents(
            [.year, .month, .day, .hour, .minute], from: date
        )
    }

    if let remindStr = remindStr, let date = parseDate(remindStr) {
        let alarm = EKAlarm(absoluteDate: date)
        reminder.addAlarm(alarm)
    }

    if let notes = notes, !notes.isEmpty {
        reminder.notes = notes
    }

    do {
        try store.save(reminder, commit: true)
        print("Created reminder: \"\(title)\" in list \"\(reminder.calendar?.title ?? "(default)")\".")
    } catch {
        fputs("Error creating reminder: \(error.localizedDescription)\n", stderr)
        exit(1)
    }
}

func cmdComplete(title: String, listName: String?) {
    var calendars: [EKCalendar]? = nil
    if let name = listName {
        guard let cal = findCalendar(named: name) else {
            fputs("Error: List \"\(name)\" not found.\n", stderr)
            exit(1)
        }
        calendars = [cal]
    }

    let reminders = fetchIncompleteReminders(in: calendars)
    let matching = reminders.filter { $0.title == title }

    if matching.isEmpty {
        print("No incomplete reminder found: \"\(title)\".")
        return
    }

    var count = 0
    for r in matching {
        r.isCompleted = true
        do {
            try store.save(r, commit: true)
            count += 1
        } catch {
            fputs("Error completing reminder: \(error.localizedDescription)\n", stderr)
        }
    }

    print("Completed \(count) reminder(s): \"\(title)\".")
}

func cmdDelete(title: String, listName: String?) {
    var calendars: [EKCalendar]? = nil
    if let name = listName {
        guard let cal = findCalendar(named: name) else {
            fputs("Error: List \"\(name)\" not found.\n", stderr)
            exit(1)
        }
        calendars = [cal]
    }

    let reminders = fetchIncompleteReminders(in: calendars)
    let matching = reminders.filter { $0.title == title }

    if matching.isEmpty {
        print("No matching reminder found: \"\(title)\".")
        return
    }

    var count = 0
    for r in matching {
        do {
            try store.remove(r, commit: true)
            count += 1
        } catch {
            fputs("Error deleting reminder: \(error.localizedDescription)\n", stderr)
        }
    }

    print("Deleted \(count) reminder(s): \"\(title)\".")
}

// MARK: - Argument Parsing

func printUsage() {
    let usage = """
    Reminders.app CLI (EventKit)

    Usage: reminders <command> [options] [arguments]

    Commands:
      lists                              List all reminder lists
      list [listname]                    List reminders (incomplete only)
      today                              Show reminders due today
      upcoming [days]                    Show reminders due in next N days (default: 7)
      overdue                            Show overdue incomplete reminders
      search "keyword"                   Search reminders by name or body
      create "Title" [options]           Create a new reminder
      complete "Title" [--list "Name"]   Mark a reminder as complete
      delete "Title" [--list "Name"]     Delete a reminder

    Options:
      -n <count>                  Max results (default: 20)
      --list "Name"               Target list
      --due "YYYY-MM-DD [HH:MM]" Due date
      --remind "YYYY-MM-DD HH:MM" Remind me date
      --notes "Text"              Notes body
      --priority <0-9>            Priority: 0=none, 1-4=high, 5=medium, 6-9=low
    """
    fputs(usage + "\n", stderr)
}

// MARK: - Main

let args = Array(CommandLine.arguments.dropFirst())
guard !args.isEmpty else {
    printUsage()
    exit(1)
}

let command = args[0]
var remaining = Array(args.dropFirst())

// Parse common options
var maxResults = 20
var parsedArgs: [String] = []

var idx = 0
while idx < remaining.count {
    switch remaining[idx] {
    case "-n":
        idx += 1
        if idx < remaining.count, let n = Int(remaining[idx]) {
            maxResults = n
        }
    default:
        parsedArgs.append(remaining[idx])
    }
    idx += 1
}

requestAccess()

switch command {
case "lists":
    cmdLists()

case "list":
    let listName = parsedArgs.first
    cmdList(listName: listName, maxResults: maxResults)

case "today":
    cmdToday(maxResults: maxResults)

case "upcoming":
    let days = parsedArgs.first.flatMap { Int($0) } ?? 7
    cmdUpcoming(days: days, maxResults: maxResults)

case "overdue":
    cmdOverdue(maxResults: maxResults)

case "search":
    guard let keyword = parsedArgs.first else {
        fputs("Usage: reminders search \"keyword\" [-n count]\n", stderr)
        exit(1)
    }
    cmdSearch(keyword: keyword, maxResults: maxResults)

case "create":
    // Re-parse remaining for create-specific options
    var title = ""
    var listName: String?
    var dueStr: String?
    var remindStr: String?
    var notes: String?
    var priority = 0
    var positional: [String] = []

    var i = 0
    let createArgs = Array(args.dropFirst())
    while i < createArgs.count {
        switch createArgs[i] {
        case "-n":       i += 2; continue
        case "--list":   i += 1; if i < createArgs.count { listName = createArgs[i] }
        case "--due":    i += 1; if i < createArgs.count { dueStr = createArgs[i] }
        case "--remind": i += 1; if i < createArgs.count { remindStr = createArgs[i] }
        case "--notes":  i += 1; if i < createArgs.count { notes = createArgs[i] }
        case "--priority": i += 1; if i < createArgs.count { priority = Int(createArgs[i]) ?? 0 }
        default:         positional.append(createArgs[i])
        }
        i += 1
    }

    title = positional.first ?? ""
    guard !title.isEmpty else {
        fputs("Usage: reminders create \"Title\" [--list \"Name\"] [--due \"YYYY-MM-DD [HH:MM]\"] [--notes \"Text\"] [--priority 0-9]\n", stderr)
        exit(1)
    }

    cmdCreate(title: title, listName: listName, dueStr: dueStr, remindStr: remindStr, notes: notes, priority: priority)

case "complete":
    var title = ""
    var listName: String?
    var positional: [String] = []

    var i = 0
    let completeArgs = Array(args.dropFirst())
    while i < completeArgs.count {
        switch completeArgs[i] {
        case "-n":     i += 2; continue
        case "--list": i += 1; if i < completeArgs.count { listName = completeArgs[i] }
        default:       positional.append(completeArgs[i])
        }
        i += 1
    }

    title = positional.first ?? ""
    guard !title.isEmpty else {
        fputs("Usage: reminders complete \"Title\" [--list \"Name\"]\n", stderr)
        exit(1)
    }

    cmdComplete(title: title, listName: listName)

case "delete":
    var title = ""
    var listName: String?
    var positional: [String] = []

    var i = 0
    let deleteArgs = Array(args.dropFirst())
    while i < deleteArgs.count {
        switch deleteArgs[i] {
        case "-n":     i += 2; continue
        case "--list": i += 1; if i < deleteArgs.count { listName = deleteArgs[i] }
        default:       positional.append(deleteArgs[i])
        }
        i += 1
    }

    title = positional.first ?? ""
    guard !title.isEmpty else {
        fputs("Usage: reminders delete \"Title\" [--list \"Name\"]\n", stderr)
        exit(1)
    }

    cmdDelete(title: title, listName: listName)

case "help", "-h", "--help":
    printUsage()

default:
    fputs("Unknown command: \(command)\n", stderr)
    printUsage()
    exit(1)
}
