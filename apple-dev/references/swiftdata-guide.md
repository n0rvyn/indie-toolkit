# SwiftData Best Practices
<!-- SECTION MARKERS: Each "section" comment line immediately precedes the ##
     heading it labels. Use Grep("<!-- section:", file) to find sections, then
     Read(file, offset, limit) to fetch only the relevant lines. -->

SwiftData 是 Apple 在 iOS 17+ / macOS 14+ 引入的声明式数据持久化框架，替代 Core Data。

<!-- section: 1. @Model 定义 keywords: @Model, SwiftData model, properties, optional, @Transient, @Attribute -->
## 1. @Model 定义

### 基本类型

```swift
import SwiftData

@Model
final class Item {
    var name: String
    var timestamp: Date
    var isCompleted: Bool = false  // 默认值

    init(name: String, timestamp: Date) {
        self.name = name
        self.timestamp = timestamp
    }
}
```

### 可选属性处理

```swift
@Model
final class Task {
    var title: String
    var notes: String?  // 可选
    var dueDate: Date?

    init(title: String) {
        self.title = title
    }
}
```

### 不持久化属性

```swift
@Model
final class Product {
    var name: String
    var price: Double

    @Transient var displayPrice: String {
        String(format: "$%.2f", price)
    }
}
```

### 唯一性约束

```swift
@Model
final class User {
    @Attribute(.unique) var email: String
    var name: String

    init(email: String, name: String) {
        self.email = email
        self.name = name
    }
}
```

<!-- section: 2. 关系定义 keywords: relationships, one-to-many, many-to-many, @Relationship, inverse, delete rule, cascade -->
## 2. 关系定义

### 一对多

```swift
@Model
final class Category {
    var name: String
    @Relationship(deleteRule: .cascade) var items: [Item] = []
}

@Model
final class Item {
    var name: String
    var category: Category?
}
```

**删除规则**：
- `.cascade`：删除父对象时删除所有子对象
- `.nullify`：删除父对象时将子对象的关系设为 nil（默认）
- `.deny`：如果有子对象，拒绝删除父对象

### 多对多

```swift
@Model
final class Student {
    var name: String
    var courses: [Course] = []
}

@Model
final class Course {
    var title: String
    var students: [Student] = []
}
```

### 反向关系

```swift
@Model
final class Post {
    var title: String
    @Relationship(deleteRule: .cascade, inverse: \Comment.post)
    var comments: [Comment] = []
}

@Model
final class Comment {
    var content: String
    var post: Post?
}
```

<!-- section: 3. 查询 keywords: @Query, predicate, filter, sort, FetchDescriptor, dynamic query -->
## 3. 查询

### @Query 基础

```swift
import SwiftUI
import SwiftData

struct ItemListView: View {
    @Query var items: [Item]

    var body: some View {
        List(items) { item in
            Text(item.name)
        }
    }
}
```

### Filter descriptor

```swift
// 简单过滤
@Query(filter: #Predicate<Item> { item in
    item.isCompleted == false
}) var activeItems: [Item]

// 字符串包含
@Query(filter: #Predicate<Item> { item in
    item.name.contains("important")
}) var importantItems: [Item]

// 日期范围
@Query(filter: #Predicate<Item> { item in
    item.timestamp > Date().addingTimeInterval(-86400)
}) var recentItems: [Item]

// 组合条件
@Query(filter: #Predicate<Item> { item in
    !item.isCompleted && item.priority > 5
}) var highPriorityActive: [Item]
```

### Sort descriptor

```swift
// 单字段排序
@Query(sort: \Item.timestamp, order: .reverse) var items: [Item]

// 多字段排序
@Query(sort: [
    SortDescriptor(\Item.isCompleted),
    SortDescriptor(\Item.timestamp, order: .reverse)
]) var items: [Item]
```

### 组合 Filter + Sort

```swift
@Query(
    filter: #Predicate<Item> { $0.isCompleted == false },
    sort: \Item.timestamp,
    order: .reverse
) var activeItems: [Item]
```

### 动态查询

```swift
struct ItemListView: View {
    @State private var searchText = ""

    var body: some View {
        ItemListContent(searchText: searchText)
            .searchable(text: $searchText)
    }
}

struct ItemListContent: View {
    let searchText: String

    @Query private var items: [Item]

    init(searchText: String) {
        self.searchText = searchText

        let predicate = #Predicate<Item> { item in
            searchText.isEmpty || item.name.contains(searchText)
        }

        _items = Query(filter: predicate, sort: \.timestamp)
    }

    var body: some View {
        List(items) { item in
            Text(item.name)
        }
    }
}
```

<!-- section: 4. 数据迁移 keywords: migration, versioned schema, ModelMigrationPlan, lightweight migration -->
## 4. 数据迁移

### Schema version

```swift
enum ItemSchemaV1: VersionedSchema {
    static var versionIdentifier = Schema.Version(1, 0, 0)

    static var models: [any PersistentModel.Type] {
        [Item.self]
    }

    @Model
    final class Item {
        var name: String
        var timestamp: Date
    }
}

enum ItemSchemaV2: VersionedSchema {
    static var versionIdentifier = Schema.Version(2, 0, 0)

    static var models: [any PersistentModel.Type] {
        [Item.self]
    }

    @Model
    final class Item {
        var name: String
        var timestamp: Date
        var isCompleted: Bool = false  // 新增字段
    }
}
```

### Migration plan

```swift
enum ItemMigrationPlan: SchemaMigrationPlan {
    static var schemas: [any VersionedSchema.Type] {
        [ItemSchemaV1.self, ItemSchemaV2.self]
    }

    static var stages: [MigrationStage] {
        [migrateV1toV2]
    }

    static let migrateV1toV2 = MigrationStage.custom(
        fromVersion: ItemSchemaV1.self,
        toVersion: ItemSchemaV2.self,
        willMigrate: nil,
        didMigrate: { context in
            // 数据转换逻辑（如需要）
            let items = try context.fetch(FetchDescriptor<Item>())
            for item in items {
                // 自定义迁移逻辑
            }
            try context.save()
        }
    )
}
```

### 轻量级迁移

对于简单的架构变更（添加可选字段、添加默认值），SwiftData 自动处理，无需编写 migration plan。

**支持自动迁移的场景**：
- 添加新的可选属性
- 添加带默认值的属性
- 删除属性
- 重命名实体或属性（使用 `@Attribute(.originalName:)` 标记）

<!-- section: 5. 并发安全 keywords: concurrency, ModelContext, thread safety, MainActor, background task -->
## 5. 并发安全

### @MainActor 使用

```swift
@MainActor
final class ItemService {
    private let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
    }

    func createItem(name: String) {
        let item = Item(name: name, timestamp: .now)
        modelContext.insert(item)
        try? modelContext.save()
    }

    func deleteItem(_ item: Item) {
        modelContext.delete(item)
        try? modelContext.save()
    }
}
```

### ModelContext 线程安全

```swift
// ❌ 错误：跨线程使用 ModelContext
Task.detached {
    modelContext.insert(item)  // Crash!
}

// ✅ 正确：在后台线程创建新的 ModelContext
Task.detached {
    let backgroundContext = ModelContext(modelContainer)
    let item = Item(name: "Background", timestamp: .now)
    backgroundContext.insert(item)
    try? backgroundContext.save()
}
```

### 后台任务处理

```swift
@MainActor
final class DataImportService {
    private let modelContainer: ModelContainer

    init(modelContainer: ModelContainer) {
        self.modelContainer = modelContainer
    }

    func importLargeDataset() async {
        await Task.detached { [modelContainer] in
            let context = ModelContext(modelContainer)

            // 执行大量数据插入
            for i in 0..<10000 {
                let item = Item(name: "Item \(i)", timestamp: .now)
                context.insert(item)

                // 定期保存以避免内存过大
                if i % 100 == 0 {
                    try? context.save()
                }
            }

            try? context.save()
        }.value
    }
}
```

### Actor 隔离

```swift
actor BackgroundProcessor {
    private let modelContainer: ModelContainer

    init(modelContainer: ModelContainer) {
        self.modelContainer = modelContainer
    }

    func processItems() async throws {
        let context = ModelContext(modelContainer)
        let items = try context.fetch(FetchDescriptor<Item>())

        for item in items {
            // 处理逻辑
            item.isCompleted = true
        }

        try context.save()
    }
}
```

<!-- section: 6. 性能优化 keywords: performance, lazy loading, batch, memory, optimization -->
## 6. 性能优化

### 批量操作

```swift
// ✅ 推荐：批量插入后保存
func insertBatch(_ names: [String]) {
    for name in names {
        let item = Item(name: name, timestamp: .now)
        modelContext.insert(item)
    }
    try? modelContext.save()  // 一次保存
}

// ❌ 避免：每次插入都保存
func insertOneByOne(_ names: [String]) {
    for name in names {
        let item = Item(name: name, timestamp: .now)
        modelContext.insert(item)
        try? modelContext.save()  // 性能差
    }
}
```

### 限制查询结果

```swift
// 使用 fetchLimit 避免加载过多数据
var descriptor = FetchDescriptor<Item>()
descriptor.fetchLimit = 50
let items = try? modelContext.fetch(descriptor)
```

### 惰性加载关系

SwiftData 默认惰性加载关系，只在访问时加载。保持这个默认行为。

<!-- section: 7. 测试 keywords: testing, in-memory, ModelContainer, unit test, SwiftData testing -->
## 7. 测试

### 内存数据库

```swift
@MainActor
final class ItemServiceTests: XCTestCase {
    var modelContainer: ModelContainer!
    var modelContext: ModelContext!

    override func setUp() async throws {
        // 使用内存配置进行测试
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        modelContainer = try ModelContainer(
            for: Item.self,
            configurations: config
        )
        modelContext = ModelContext(modelContainer)
    }

    func testCreateItem() {
        let item = Item(name: "Test", timestamp: .now)
        modelContext.insert(item)
        try? modelContext.save()

        let items = try? modelContext.fetch(FetchDescriptor<Item>())
        XCTAssertEqual(items?.count, 1)
    }
}
```

## 参考

- [Apple SwiftData Documentation](https://developer.apple.com/documentation/swiftdata)
- [WWDC23: Meet SwiftData](https://developer.apple.com/videos/play/wwdc2023/10187/)
- [WWDC23: Model your schema with SwiftData](https://developer.apple.com/videos/play/wwdc2023/10195/)

## Community Patterns (vendored from vabole/apple-skills)

_Inline attribution: 以下内容 vendor 自 vabole/apple-skills v1.0.10 `skills/guide-swiftdata/` (MIT, (c) 2026 Ilia Abolhasani, vendored 2026-05-14). 与本仓 above 节内容互补：本仓骨架给项目化规范；下方为社区沉淀的常见 pitfall（autosave、危险 predicate、CloudKit 约束、indexing、class inheritance）。冲突时本仓骨架为准。_

# SwiftData Patterns

Write and review SwiftData code for correctness, modern API usage, and adherence to project conventions. Report only genuine problems — do not nitpick or invent issues.

## Core Instructions

- Target Swift 6.2 or later, using modern Swift concurrency.
- Prefer SwiftData across the board. Do not suggest Core Data unless the feature cannot be solved with SwiftData.
- Do not introduce third-party frameworks without asking first.

## Review Process

1. Check for core SwiftData issues using `references/core-rules.md`.
2. Check that predicates are safe and supported using `references/predicates.md`.
3. If the project uses CloudKit, check for CloudKit-specific constraints using `references/cloudkit.md`.
4. If the project targets iOS 18+, check for indexing opportunities using `references/indexing.md`.
5. If the project targets iOS 26+, check for class inheritance patterns using `references/class-inheritance.md`.

If doing partial work, load only the relevant reference files.

## References

| Topic | Reference |
|-------|-----------|
| Autosave, relationships, delete rules, `@Query` restrictions, `#Unique`, `@Transient` | `references/core-rules.md` |
| Supported predicates, dangerous patterns that crash at runtime, unsupported methods | `references/predicates.md` |
| CloudKit constraints: no `#Unique`, optional requirements, eventual consistency | `references/cloudkit.md` |
| Database indexing (iOS 18+), single and compound property indexes | `references/indexing.md` |
| Model subclassing (iOS 26+), `@available` requirements, predicate filtering | `references/class-inheritance.md` |

## Reference Materials

### Core Rules

- When SwiftData first launched, it autosaved model contexts aggressively. Since then, autosaving happens less frequently and is now hard to predict, so many developers prefer to add explicit calls to `save()` when correctness is important.
- There is no need to check `modelContext.hasChanges` before saving; just call `save()` directly.
- `ModelContext` and model instances must never cross actor boundaries. Model containers and persistent identifiers *are* sendable, so if you need a model instance to be transferred across actors you should send its identifier and re-fetch in the destination context.
- When using `@Relationship` to define a relationship from one model to another, place the macro on one side of the relationship only. Trying to use it on both sides causes a circular reference.
- Persistent identifiers are temporary before they are saved for the first time. Temporary IDs start with a lowercase "t", and a model will be given a new ID after it is saved for the first time. As a result, you must save an object before relying on its ID.
- Do not attempt to use the property name `description` in any `@Model` class; it is explicitly disallowed.
- Do not attempt to add property observers to `@Model` classes; they will be quietly ignored.
- `@Attribute(.externalStorage)` is a *suggestion*, not a *requirement*, and only applies to properties of type `Data` – SwiftData will do what it thinks is best.
- `@Transient` properties are not persisted, and must have a default value. They reset to that default when the object is fetched from the store. If the value is derived from other stored properties, using a computed property is usually a better idea – use `@Transient` only if the value is expensive to produce.
- It is nearly always a good idea to have a specific migration schema in place, even if the project is only dealing with lightweight migrations.
- It is nearly always a good idea to have an explicit delete rule in place for relationships. This is most commonly `@Relationship(deleteRule: .cascade)`, but others are available. The default is `.nullify`, which sets the related model's reference to nil when the parent is deleted. This can leave orphaned objects or crash if the property is non-optional.
- Do not attempt to use `@Query` outside of SwiftUI views; it is designed to work specifically *inside* views, and will not operate correctly outside.
- If you only need the number of items matching a query, consider `ModelContext.fetchCount()` with a fetch descriptor. This will *not* live update if the data changes unless something else triggers the update, such as `@Query`, so it should be used carefully.
- When using `FetchDescriptor`, it may sometimes be beneficial to set the `relationshipKeyPathsForPrefetching` property. It is an empty array by default, but if you know certain relationships will be used it is more efficient to fetch them upfront.
- Similarly, you should consider setting `propertiesToFetch` so that only properties that are used are actually fetched. (It fetches all properties by default.)
- SwiftData frequently gets inverse relationships wrong, so it is almost always a good idea to be explicit with the `@Relationship` macro by specifying the exact inverse relationship.
- Do not write `#Unique` more than once per model; you can only have one, placed inside the model class. If you need multiple uniqueness constraints, pass them as separate key path arrays in a single `#Unique`, e.g. `#Unique<Foo>([\.email], [\.username])`.
- Enum properties stored in a model must conform to `Codable`. Some agents will insist that enums with associated values are not supported, but this is wrong – they work just fine.

### Working with Predicates

SwiftData predicates support only a subset of Swift functionality. Some things are marked as being unsupported, meaning that they will not build. Other things are *not* marked as unsupported and yet are still not supported, meaning that they will build but crash at runtime.

This guide contains specific guidance on what to use and when.

**String matching:** When writing a query predicate to perform string matching, always use `localizedStandardContains()` rather than trying to use `lowercased().contains()` or similar.

```swift
@Query(filter: #Predicate<Movie> {
    $0.name.localizedStandardContains("titanic")
}) private var movies: [Movie]
```

**hasPrefix():** `hasPrefix()` and `hasSuffix()` are not supported in SwiftData predicates. If you want to use `hasPrefix()`, you should use `starts(with:)` instead.

```swift
@Query(filter: #Predicate<Website> {
    $0.type.starts(with: "https://apple.com")
}) private var appleLinks: [Website]
```

**Unsupported predicates:** Many common methods have no equivalent in SwiftData, and will not compile. For example, all these common operations are not supported:
- `String.hasSuffix()`
- `String.lowercased()`
- `Sequence.map()`
- `Sequence.reduce()`
- `Sequence.count(where:)`
- `Collection.first`

Custom operators are also not allowed.

**Dangerous predicates:** Some SwiftData predicates will compile cleanly then fail or even crash at runtime.

For example, this is a valid predicate designed to show only movies that have a non-empty cast list:

```swift
@Query(filter: #Predicate<Movie> { !$0.cast.isEmpty }, sort: \Movie.name) private var movies: [Movie]
```

However, *this* query looks like it does the same thing, but will crash at runtime:

```swift
@Query(filter: #Predicate<Movie> { $0.cast.isEmpty == false }, sort: \Movie.name) private var movies: [Movie]
```

Never attempt to create query predicates that use computed properties, `@Transient` properties, or use custom `Codable` struct data. They might compile cleanly, but they will crash at runtime.

All predicates must rely on data that is actually stored in the database as `@Model` classes.

Never attempt to use regular expressions in predicates. They will compile cleanly then fail at runtime.

### Using SwiftData with CloudKit

**These rules only apply if the project is configured to use SwiftData with CloudKit.**

- Never use `@Attribute(.unique)` or `#Unique`; they are *not* supported in CloudKit, and when used will cause local data to fail too.
- All model properties must always either have default values or be marked as optional.
- All relationships must be marked optional.
- Indexes and subclasses are supported in CloudKit, as long as the correct OS release is used.

Keep in mind that CloudKit is designed for *eventual consistency* – any SwiftData code written with CloudKit support must be able to function if data has yet to synchronize.

### Indexing

When supporting iOS 18 and other coordinated releases, SwiftData supports indexes to help speed up queries. This has a small performance cost for writing, so if data is read rarely and updated frequently (such as logging), indexes may be a bad choice.

Indexes can be on single properties, like this:

```swift
@Model class Article {
    #Index<Article>([\.type], [\.author])

    var type: String
    var author: String
    var publishDate: Date

    init(type: String, author: String, publishDate: Date) {
        self.type = type
        self.author = author
        self.publishDate = publishDate
    }
}
```

Alternatively, you can mix single properties and groups of properties when you know they are often used together:

```swift
#Index<Article>([\.type], [\.type, \.author])
```

### Class Inheritance

When supporting iOS 26 and other coordinated releases (macOS 26, etc), SwiftData supports class inheritance for models.

**Important:** This is not a common feature; only add model subclassing if it actually has a benefit. Alternatives such as protocols are often simpler and better.

This works the same as regular class inheritance in Swift, however, child classes must be explicitly marked `@available` for a 26 release or later, e.g. iOS 26. This is required even if iOS 26 is set as the minimum deployment target.

For example:

```swift
@Model class Article {
    var type: String

    init(type: String) {
        self.type = type
    }
}

@available(iOS 26, *)
@Model class Tutorial: Article {
    var difficulty: Int

    init(difficulty: Int) {
        self.difficulty = difficulty
        super.init(type: "Tutorial")
    }
}
```

Notice how both the parent and child classes must use the `@Model` macro.

When providing the schemas as part of model container creation, make sure to list both the parent class and its child classes – SwiftData is *not* able to infer the connection by itself.

If you create a relationship to a model that has subclasses, the relationship might contain the parent class or any of its subclasses. If you want to load specific child classes but not the parent class, use `is` with the `#Predicate` macro to perform filtering:

```swift
@Query(filter: #Predicate<Article> {
    $0 is Tutorial || $0 is News
}) private var tutorialsAndNews: [Article]
```

**Important:** The type of the resulting array elements is `Article`, the parent class, so typecasting must be used to access child-class properties and methods.

