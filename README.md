# SFU CourseBot

A Discord Bot to show information about SFU courses.

Works with both '!' prefix commands and discord built-in / commands.

[Invite this bot to Server](https://discord.com/oauth2/authorize?client_id=1429023672772853841&permissions=2147503104&integration_type=0&scope=bot+applications.commands)
## Usage/Examples

### Course Command
The !course command retrieves detailed informatio nabout a specific course.

**Usage:**
```
/course <subject: str> <course_number: str>
```
**Parameters:**
- `subject`: The department code (e.g., `cmpt`, `math`, `engl`)
- `course_number`: The course number (e.g., `120`, `225`, `105w`)

**Examples:**
```
- /course CMPT 201
- /course CMPT 105w
- /course MACM 201
```

### Offerings Command
The `!offerings` command retrieves course offerings taught by a specific instructor.

**Usage:**
```
!offerings <instructor_name: str> <term: str>
```

**Parameters:**
- `instructor_name`: The instructor's full name (use quotes for names with spaces)
- `term` (optional): Filter by specific term (e.g., `fall`, `spring 2024`, `summer`)

**Examples:**
```
!instructor "Brian Fraser"
!instructor "John Smith" fall
!instructor "Jane Doe" "spring 2024"
!instructor Edgar summer
```

**Notes:**
- If multiple instructors match your search, the bot will show a list and ask you to be more specific
- Use quotation marks around names with spaces for exact matches
- Term filtering is case-insensitive and supports partial matches
- Without a term filter, all course offerings for the instructor will be shown

### Sections Command
The `!sections` command retrieves all available sections for a specific course in a given term.

**Usage:**
```
/sections <year:int> <term: str> <dept: str> <number: int>
```

**Parameters:**
- `year`: The year to search (YYYY) (e.g., `2026`, `2025`, `2019`)
- `term`: The term/season to search in (e.g., `fall`, `spring`, `summer`)
- `dept`: The department (e.g., `cmpt`, `math`, `engl`)
- `number`: The course number (e.g., `120`, `225`, `105w`)

**Examples:**
```
/sections 2024 fall CMPT 120 
/sections 2020 spring MATH 151
/sections 2026 summer ENGL 199 
```

**Notes:**
- Shows section details including instructor, schedule, and enrollment status
- Term is case-insensitive
- Parameters may require quotations

### Reviews Command
The `!reviews` command retrieves instructor reviews and ratings.

**Usage:**
```
/reviews <instructor_name: str>
```

**Parameters:**
- `instructor_name`: The instructor's full name (use quotes for names with spaces)

**Examples:**
```
!reviews "Brian Fraser"
!reviews "John Smith"
/reviews Edgar
```

**Notes:**
- Displays ratings and review information for the specified instructor
- If multiple instructors match your search, the bot will show a list and ask you to be more specific
- Use quotation marks around names with spaces for exact matches

## Acknowledgements

 - [SFU COURSES API](https://api.sfucourses.com/) by Brian Rahadi. This is where I get my course info from.
 - Discord documentation was clutch
## Authors

- [@smehars](https://www.github.com/smehars)


## Feedback

If you have any feedback or questions, please reach out to me at meharsaini@hotmail.com.

## Study Time Railguards

### Setup

#### Roles

1. Create a Role to automatically assign to users for Study Time
2. Ensure the bot role is above the Study Time assigned role

#### Environment

See `.env.template`
