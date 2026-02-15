#!/usr/bin/env swift

import EventKit
import Foundation

// MARK: - Configuration

let store = EKEventStore()
let dtFmt: DateFormatter = {
    let f = DateFormatter()
    f.dateFormat = "yyyy-MM-dd HH:mm"
    f.locale = Locale(identifier: "en_US_POSIX")
    return f
}()
let dateFmt: DateFormatter = {
    let f = DateFormatter()
    f.dateFormat = "yyyy-MM-dd"
    f.locale = Locale(identifier: "en_US_POSIX")
    return f
}()

// MARK: - Helpers

func requestAccess() {
    let semaphore = DispatchSemaphore(value: 0)
    var granted = false

    if #available(macOS 14.0, *) {
        store.requestFullAccessToEvents { g, error in
            granted = g
            if let error = error {
                fputs("Error requesting access: \(error.localizedDescription)\n", stderr)
            }
            semaphore.signal()
        }
    } else {
        store.requestAccess(to: .event) { g, error in
            granted = g
            if let error = error {
                fputs("Error requesting access: \(error.localizedDescription)\n", stderr)
            }
            semaphore.signal()
        }
    }

    semaphore.wait()

    guard granted else {
        fputs("Error: Calendar access not granted. Enable in System Settings > Privacy & Security > Calendars.\n", stderr)
        exit(1)
    }
}

func findCalendar(named name: String) -> EKCalendar? {
    store.calendars(for: .event).first { $0.title == name }
}

func parseDateTime(_ str: String) -> Date? {
    if let d = dtFmt.date(from: str) { return d }
    if let d = dateFmt.date(from: str) { return d }
    return nil
}

func isDateOnly(_ str: String) -> Bool {
    str.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil
}

func formatDate(_ date: Date) -> String {
    dtFmt.string(from: date)
}

func hexColor(from cgColor: CGColor) -> String {
    guard let components = cgColor.components, components.count >= 3 else { return "#000000" }
    let r = Int(components[0] * 255)
    let g = Int(components[1] * 255)
    let b = Int(components[2] * 255)
    return String(format: "#%02x%02x%02x", r, g, b)
}

func printEvents(_ events: [EKEvent], maxResults: Int) {
    if events.isEmpty {
        print("No events found.")
        return
    }

    // Sort by start date
    let sorted = events.sorted { $0.startDate < $1.startDate }
    let limit = min(sorted.count, maxResults)

    for i in 0..<limit {
        let e = sorted[i]
        let title = e.title ?? "(untitled)"
        let calName = e.calendar?.title ?? "(unknown)"

        let dateStr: String
        if e.isAllDay {
            dateStr = dateFmt.string(from: e.startDate) + " (all-day)"
        } else {
            dateStr = formatDate(e.startDate) + " - " + formatDate(e.endDate)
        }

        let location = e.location ?? ""

        print("\(i + 1). \(title)")
        var details = "   Calendar: \(calName) | Date: \(dateStr)"
        if !location.isEmpty { details += " | Location: \(location)" }
        print(details)
        print("")
    }

    print("--- \(limit) event(s) shown (max \(maxResults)) ---")
}

// MARK: - Commands

func cmdCalendars() {
    let calendars = store.calendars(for: .event)
    for (idx, cal) in calendars.enumerated() {
        let writable = cal.allowsContentModifications ? "writable" : "read-only"
        let color = hexColor(from: cal.cgColor)

        print("\(idx + 1). \(cal.title)")
        var details = "   Color: \(color) | \(writable)"
        if let source = cal.source {
            details += " | Source: \(source.title)"
        }
        print(details)
        print("")
    }
}

func cmdToday(maxResults: Int) {
    let cal = Calendar.current
    let startOfDay = cal.startOfDay(for: Date())
    let endOfDay = cal.date(byAdding: .day, value: 1, to: startOfDay)!

    let predicate = store.predicateForEvents(withStart: startOfDay, end: endOfDay, calendars: nil)
    let events = store.events(matching: predicate)
    printEvents(events, maxResults: maxResults)
}

func cmdUpcoming(days: Int, maxResults: Int) {
    let cal = Calendar.current
    let startOfDay = cal.startOfDay(for: Date())
    let endDate = cal.date(byAdding: .day, value: days, to: startOfDay)!

    let predicate = store.predicateForEvents(withStart: startOfDay, end: endDate, calendars: nil)
    let events = store.events(matching: predicate)
    printEvents(events, maxResults: maxResults)
}

func cmdSearch(keyword: String, maxResults: Int) {
    // Search within a wide range: 1 year back to 1 year ahead
    let cal = Calendar.current
    let start = cal.date(byAdding: .year, value: -1, to: Date())!
    let end = cal.date(byAdding: .year, value: 1, to: Date())!

    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
    let events = store.events(matching: predicate)

    let lower = keyword.lowercased()
    let matching = events.filter { e in
        let title = (e.title ?? "").lowercased()
        let location = (e.location ?? "").lowercased()
        let notes = (e.notes ?? "").lowercased()
        return title.contains(lower) || location.contains(lower) || notes.contains(lower)
    }

    printEvents(matching, maxResults: maxResults)
}

func cmdCreate(title: String, startStr: String, endStr: String, calendarName: String?, location: String?, notes: String?) {
    guard let startDate = parseDateTime(startStr) else {
        fputs("Error: Invalid start date format. Use \"YYYY-MM-DD HH:MM\" or \"YYYY-MM-DD\".\n", stderr)
        exit(1)
    }
    guard let endDate = parseDateTime(endStr) else {
        fputs("Error: Invalid end date format. Use \"YYYY-MM-DD HH:MM\" or \"YYYY-MM-DD\".\n", stderr)
        exit(1)
    }

    let event = EKEvent(eventStore: store)
    event.title = title
    event.startDate = startDate
    event.endDate = endDate
    event.isAllDay = isDateOnly(startStr) && isDateOnly(endStr)

    if let name = calendarName {
        guard let cal = findCalendar(named: name) else {
            fputs("Error: Calendar \"\(name)\" not found.\n", stderr)
            exit(1)
        }
        event.calendar = cal
    } else {
        event.calendar = store.defaultCalendarForNewEvents
    }

    if let loc = location, !loc.isEmpty {
        event.location = loc
    }
    if let n = notes, !n.isEmpty {
        event.notes = n
    }

    do {
        try store.save(event, span: .thisEvent)
        let dateDisplay = event.isAllDay
            ? dateFmt.string(from: event.startDate) + " (all-day)"
            : formatDate(event.startDate)
        print("Event created: \"\(title)\" on \(dateDisplay) in calendar \"\(event.calendar?.title ?? "(default)")\".")
    } catch {
        fputs("Error creating event: \(error.localizedDescription)\n", stderr)
        exit(1)
    }
}

func cmdDelete(title: String, dateStr: String) {
    guard let dayStart = dateFmt.date(from: dateStr) else {
        fputs("Error: Date must be in YYYY-MM-DD format.\n", stderr)
        exit(1)
    }

    let cal = Calendar.current
    let dayEnd = cal.date(byAdding: .day, value: 1, to: dayStart)!

    let predicate = store.predicateForEvents(withStart: dayStart, end: dayEnd, calendars: nil)
    let events = store.events(matching: predicate)
    let matching = events.filter { $0.title == title && $0.calendar.allowsContentModifications }

    if matching.isEmpty {
        print("No matching event found: \"\(title)\" on \(dateStr).")
        return
    }

    var count = 0
    for event in matching {
        do {
            try store.remove(event, span: .thisEvent)
            count += 1
        } catch {
            fputs("Error deleting event: \(error.localizedDescription)\n", stderr)
        }
    }

    print("Deleted \(count) event(s): \"\(title)\" on \(dateStr).")
}

// MARK: - Usage

func printUsage() {
    let usage = """
    Calendar CLI (EventKit)

    Usage: calendar <command> [options] [arguments]

    Commands:
      calendars                      List all calendars
      today                          Show today's events
      upcoming [days]                Show events for next N days (default: 7)
      search "keyword"               Search events by title, location, or notes
      create "Title" "Start" "End" [options]   Create a new event
      delete "Event Title" "YYYY-MM-DD"        Delete an event

    Options:
      -n <count>           Max results (default: 20)
      --calendar "Name"    Target calendar (create only)
      --location "Place"   Event location (create only)
      --notes "Text"       Event notes (create only)

    Date formats:
      "YYYY-MM-DD HH:MM"  Timed event
      "YYYY-MM-DD"         All-day event
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
case "calendars":
    cmdCalendars()

case "today":
    cmdToday(maxResults: maxResults)

case "upcoming":
    let days = parsedArgs.first.flatMap { Int($0) } ?? 7
    cmdUpcoming(days: days, maxResults: maxResults)

case "search":
    guard let keyword = parsedArgs.first else {
        fputs("Usage: calendar search \"keyword\" [-n count]\n", stderr)
        exit(1)
    }
    cmdSearch(keyword: keyword, maxResults: maxResults)

case "create":
    var title = ""
    var startStr = ""
    var endStr = ""
    var calendarName: String?
    var location: String?
    var notes: String?
    var positional: [String] = []

    var i = 0
    let createArgs = Array(args.dropFirst())
    while i < createArgs.count {
        switch createArgs[i] {
        case "-n":         i += 2; continue
        case "--calendar": i += 1; if i < createArgs.count { calendarName = createArgs[i] }
        case "--location": i += 1; if i < createArgs.count { location = createArgs[i] }
        case "--notes":    i += 1; if i < createArgs.count { notes = createArgs[i] }
        default:           positional.append(createArgs[i])
        }
        i += 1
    }

    title = positional.count > 0 ? positional[0] : ""
    startStr = positional.count > 1 ? positional[1] : ""
    endStr = positional.count > 2 ? positional[2] : ""

    guard !title.isEmpty, !startStr.isEmpty, !endStr.isEmpty else {
        fputs("Usage: calendar create \"Title\" \"Start\" \"End\" [--calendar \"Name\"] [--location \"Place\"] [--notes \"Text\"]\n", stderr)
        exit(1)
    }

    cmdCreate(title: title, startStr: startStr, endStr: endStr, calendarName: calendarName, location: location, notes: notes)

case "delete":
    let title = parsedArgs.count > 0 ? parsedArgs[0] : ""
    let dateStr = parsedArgs.count > 1 ? parsedArgs[1] : ""

    guard !title.isEmpty, !dateStr.isEmpty else {
        fputs("Usage: calendar delete \"Event Title\" \"YYYY-MM-DD\"\n", stderr)
        exit(1)
    }

    cmdDelete(title: title, dateStr: dateStr)

case "help", "-h", "--help":
    printUsage()

default:
    fputs("Unknown command: \(command)\n", stderr)
    printUsage()
    exit(1)
}
