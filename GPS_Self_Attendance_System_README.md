# GPS Self-Attendance System

A web-based GPS Self-Attendance System that allows students to mark
their own attendance using their mobile device while ensuring that they
are physically present inside the classroom.

The system is built around three hard requirements:

1.  **A 10-metre attendance radius.** The geofence is configured at
    `10` metres — classroom-level, not campus-level.
2.  **No practical opportunity for proxy attendance.** Location alone
    cannot deliver this, so the system requires several independent
    proofs of presence at once (see
    [Anti-Proxy Design](#anti-proxy-design)).
3.  **Attendance is possible only while the teacher has switched it
    on.** There is no always-open endpoint. If no session is `ACTIVE`,
    every attendance request is refused for every student.

The system uses the **HTML5 Geolocation API** to obtain the student's
current latitude and longitude and applies **geofencing** to determine
whether the student is within the attendance radius. GPS is combined
with a **rotating one-time session token**, **classroom network
verification**, and **device binding**, so that no single spoofable
signal can produce an attendance record on its own.

> **Design note.** A 10-metre radius is smaller than typical smartphone
> GPS error, and GPS coordinates can be faked outright by a mock-location
> app. This document therefore does not treat GPS as the anti-proxy
> mechanism. GPS is a coarse sanity check; the short-range signals
> (rotating token, classroom network, bound device) are what actually
> pin the student to the room. The
> [Attendance Validation Rules](#attendance-validation-rules) and
> [Anti-Proxy Design](#anti-proxy-design) sections explain exactly how
> the 10-metre requirement is enforced without falsely rejecting
> students who are genuinely present.

------------------------------------------------------------------------

## Table of Contents

-   [Overview](#overview)
-   [Problem Statement](#problem-statement)
-   [Objectives](#objectives)
-   [Key Features](#key-features)
-   [System Users](#system-users)
-   [System Workflow](#system-workflow)
-   [Proposed System](#proposed-system)
-   [Architecture](#architecture)
-   [Technology Stack](#technology-stack)
-   [Functional Requirements](#functional-requirements)
-   [Non-Functional Requirements](#non-functional-requirements)
-   [GPS and Geofencing](#gps-and-geofencing)
-   [Distance Calculation](#distance-calculation)
-   [Teacher-Controlled Attendance Window](#teacher-controlled-attendance-window)
-   [Anti-Proxy Design](#anti-proxy-design)
-   [Database Design](#database-design)
-   [Suggested Database Schema](#suggested-database-schema)
-   [Application Modules](#application-modules)
-   [Teacher Workflow](#teacher-workflow)
-   [Student Workflow](#student-workflow)
-   [Admin Workflow](#admin-workflow)
-   [API Design](#api-design)
-   [Project Structure](#project-structure)
-   [Installation and Setup](#installation-and-setup)
-   [Configuration](#configuration)
-   [Running the Project](#running-the-project)
-   [Example Attendance Result](#example-attendance-result)
-   [Attendance Validation Rules](#attendance-validation-rules)
-   [Security Considerations](#security-considerations)
-   [Advantages](#advantages)
-   [Limitations](#limitations)
-   [Future Scope](#future-scope)
-   [Testing](#testing)
-   [Sample Test Cases](#sample-test-cases)
-   [Project Report Structure](#project-report-structure)
-   [Conclusion](#conclusion)

------------------------------------------------------------------------

## Overview

Traditional attendance systems often require teachers to manually call
student names or maintain paper-based attendance records. This can
consume classroom time, introduce human errors, and make it difficult to
generate attendance reports.

The GPS Self-Attendance System provides a digital alternative.

A typical attendance flow is:

``` text
Teacher presses "Open Attendance"      <-- nothing below is possible
     |                                     until this happens
     v
Session becomes ACTIVE for N seconds
Rotating QR token starts displaying
     |
     v
Student Login (bound device only)
     |
     v
Open Attendance Page
     |
     v
Scan Teacher's Rotating QR Code
     |
     v
Allow GPS Permission
     |
     v
Get Current Latitude & Longitude
     |
     v
Send token + coordinates + device id
     |
     v
+--------- SERVER-SIDE CHECKS ---------+
| 1. Session ACTIVE and inside window  |
| 2. Token valid, unexpired, unused    |
| 3. Request from classroom network    |
| 4. Device bound to this student      |
| 5. Device not already used this      |
|    session by someone else           |
| 6. GPS accuracy acceptable           |
| 7. Distance within 10 m geofence     |
| 8. Student enrolled in the class     |
| 9. No duplicate record               |
+--------------------------------------+
     |
     +----------------------+
     |                      |
  All pass             Any check fails
     |                      |
     v                      v
Record Attendance      Reject + log attempt
     |                      |
     v                      v
Show Success Message   Show reason to student
                       Flag to teacher's live roster
```

The system can support three major interfaces:

1.  **Student Application** - used to mark and view attendance.
2.  **Teacher Application/Panel** - used to create attendance sessions
    and manage class attendance.
3.  **Admin Panel** - used to manage the overall system, locations,
    users, departments, subjects, and reports.

------------------------------------------------------------------------

## Problem Statement

Manual attendance management has several problems:

-   It takes classroom time.
-   Attendance records can contain human errors.
-   Maintaining paper records is difficult.
-   Generating monthly or student-wise reports takes additional effort.
-   Proxy attendance can be difficult to control.
-   Students may attempt to mark attendance when they are outside the
    authorized location.
-   Attendance data is not always immediately available to teachers and
    administrators.

The proposed system addresses these issues by combining digital
attendance management with GPS-based location verification.

------------------------------------------------------------------------

## Objectives

The main objectives of the project are:

-   Allow students to mark attendance using their mobile phones.
-   Verify the student's current physical location.
-   Use a **10-metre** geofence around the classroom.
-   Allow attendance **only while the teacher has opened the window**.
-   Make proxy attendance impractical by requiring several independent
    proofs of presence rather than location alone.
-   Automatically record attendance date and time.
-   Store the student's location at the time of attendance.
-   Prevent duplicate attendance for the same session.
-   Prevent one device from marking attendance for multiple students.
-   Log every attendance attempt, including rejected ones.
-   Provide teachers with live attendance information and overrides.
-   Provide administrators with centralized management.
-   Generate daily, monthly, class-wise, and student-wise reports.
-   Export attendance records to Excel/CSV and PDF.
-   Reduce manual attendance work and improve record accuracy.

------------------------------------------------------------------------

# Key Features

## Student Features

-   Student registration and login.
-   Secure authentication.
-   One-time device registration (account is bound to that device).
-   View assigned classes and subjects.
-   See attendance sessions only while a teacher has one open.
-   Scan the teacher's rotating QR code to obtain a one-time token.
-   GPS-based attendance check-in inside a 10-metre geofence.
-   Automatic date and time recording.
-   Attendance history.
-   Personal attendance percentage.
-   View attendance status.
-   Duplicate attendance prevention.
-   Clear, specific rejection reasons (window closed, token expired,
    wrong network, outside radius, unregistered device).

## Teacher Features

-   Teacher login.
-   Create or select classes.
-   Select subjects.
-   Create an attendance session.
-   **Open and close the attendance window manually** — the single
    switch that makes student check-in possible at all.
-   Configure the attendance window length (default 120 seconds).
-   Display the rotating QR code on the classroom screen.
-   Configure/select the attendance location.
-   Watch the live roster fill as students mark in.
-   See rejected and flagged attempts in real time.
-   Approve, reject, or manually override any record.
-   Approve device-change requests for their students.
-   View attendance reports.
-   Filter attendance by date, class, or subject.

## Admin Features

-   Admin authentication.
-   Manage students.
-   Manage teachers.
-   Manage departments.
-   Manage classes.
-   Manage subjects.
-   Create college/classroom GPS locations.
-   Configure the attendance radius (default and recommended: 10 m).
-   Register classroom networks (allowed egress IP / Wi-Fi BSSID).
-   Configure GPS accuracy threshold and token lifetime.
-   Manage device bindings and reset a student's device.
-   Review flagged/anomalous attempts.
-   Generate daily reports.
-   Generate monthly reports.
-   Generate student-wise reports.
-   Export attendance to Excel/CSV.
-   Export attendance to PDF.

------------------------------------------------------------------------

# System Users

  User      Main Responsibilities
  --------- ------------------------------------------------------------
  Student   Register device, scan QR, verify GPS, mark attendance
  Teacher   Open/close the attendance window, monitor live roster,
            override, manage attendance
  Admin     Manage users, locations, networks, devices, radius, reports

------------------------------------------------------------------------

# System Workflow

## Step 1 - Teacher Starts Attendance

The teacher logs into the teacher panel and selects:

-   Class
-   Subject
-   Attendance location
-   Attendance date/session

The teacher then creates the session and, when ready, presses
**Open Attendance**.

This is the gate for the entire system. Creating a session does *not*
allow anybody to mark attendance. Only pressing **Open Attendance**
moves the session to `ACTIVE` and starts the countdown window.

Example:

``` text
Class: B.Tech CSE - 3rd Year
Subject: Data Structures
Location: Computer Science Block (10 m radius)
Session: 10:00 AM - 11:00 AM

Attendance window : CLOSED
                    [ Open Attendance ]
```

After the teacher presses the button:

``` text
Attendance window : OPEN
Closes in         : 01:53

QR code rotating every 30 seconds
Marked so far     : 0 / 62
```

When the countdown reaches zero — or the teacher presses
**Close Attendance** — the window shuts and no further attendance can be
recorded, regardless of where the student is standing.

------------------------------------------------------------------------

## Step 2 - Student Opens the Application

The student logs into the application. What they see depends entirely on
whether a teacher has opened the window.

While the window is closed:

``` text
No attendance session is currently open.

Your teacher has not started attendance yet.
```

The **Mark Attendance** button does not exist in this state — and even if
the request is crafted by hand, the server refuses it.

Once the teacher opens the window:

``` text
Subject: Data Structures
Teacher: Mr. Sharma
Class: CSE 3rd Year

Window closes in: 01:47

[ Scan QR & Mark Attendance ]
```

------------------------------------------------------------------------

## Step 3 - GPS Permission

When the student presses **Mark Attendance**, the application requests
access to the device location.

The browser/mobile device obtains:

``` text
Latitude
Longitude
GPS Accuracy
```

The application should handle cases where:

-   GPS permission is denied.
-   Location services are disabled.
-   GPS coordinates cannot be obtained.
-   The reported accuracy is too poor.

------------------------------------------------------------------------

## Step 4 - Server-Side Location Verification

The student's coordinates, scanned token, and device identifier are sent
to the backend.

The backend compares the coordinates with the configured classroom
location.

Example:

``` text
Classroom Location
Latitude  : 28.613900
Longitude : 77.209000

Student Location
Latitude  : 28.613935
Longitude : 77.209021

Allowed Radius : 10 metres
GPS Accuracy   : 8.4 metres
```

The backend calculates the distance between both coordinates using the
Haversine formula and applies the accuracy-aware comparison described in
[Distance Calculation](#distance-calculation).

------------------------------------------------------------------------

## Step 5 - Attendance Validation

The geofence test is:

``` text
distance - min(accuracy, ACCURACY_CREDIT) <= 10
```

but passing it is not sufficient on its own. The server evaluates the
full chain, in this order, and stops at the first failure:

-   Is the student authenticated?
-   **Is the attendance window OPEN right now?** (teacher gate)
-   Is the token present, unexpired, and issued by this session?
-   Did the request arrive from the registered classroom network?
-   Is the device bound to this student account?
-   Has this device already marked attendance for someone else in this
    session?
-   Is the student enrolled in the class?
-   Are the coordinates well-formed and not flagged as mock locations?
-   Is the GPS accuracy within the configured threshold?
-   Is the location within the 10-metre geofence?
-   Has the student already marked attendance?

If every check passes, attendance is recorded. Every failure is also
written to the attempt log and surfaced on the teacher's live roster.

------------------------------------------------------------------------

## Step 6 - Attendance Recorded

A successful record may contain:

``` text
Student ID
Session ID
Date
Time
Latitude
Longitude
GPS Accuracy
Distance
Device ID
Token ID
Source IP
Verification Flags
Status
```

Example:

``` text
Student Name : Gaurav Roy
Roll Number  : 101

Distance from Classroom : 4.2 metres
Allowed Radius          : 10 metres

Verified : window OPEN, token OK, network OK, device OK

Status : PRESENT

Date : 17-08-2026
Time : 11:25 AM
```

------------------------------------------------------------------------

# Proposed System

The proposed system consists of three main interfaces.

## 1. Student App

``` text
Student Login/Register
        |
        v
Student Dashboard
        |
        +---- View Attendance
        |
        +---- Attendance History
        |
        +---- Open Window? (teacher-controlled)
                    |
              +-----+-----+
              |           |
             No          Yes
              |           |
              v           v
         "Not open"   Scan QR Token
                          |
                          v
                    Get GPS Location
                          |
                          v
                 Server Verification Chain
                          |
                +---------+---------+
                |                   |
             Valid                 Invalid
                |                   |
                v                   v
            Attendance         Rejected with
             Recorded          specific reason
```

### Student App Functions

-   Student login/register
-   One-time device registration
-   QR token scanning
-   GPS-based attendance check-in
-   10 m classroom geofence verification
-   Automatic date and time recording
-   Personal attendance percentage
-   Attendance history

------------------------------------------------------------------------

## 2. Teacher App/Panel

``` text
Teacher Login
      |
      v
Teacher Dashboard
      |
      +---- Select Class
      |
      +---- Select Subject
      |
      +---- Create Session      (SCHEDULED)
      |
      v
  [ OPEN ATTENDANCE ]           (ACTIVE - the gate)
      |
      v
Display Rotating QR Code
      |
      v
Students Mark Attendance
      |
      v
Live Roster
      |
      +---- Marked / Rejected / Flagged
      |
      +---- Approve/Override
      |
      v
  [ CLOSE ATTENDANCE ]          (CLOSED - terminal)
      |
      +---- Generate Report
```

### Teacher Functions

-   Teacher login
-   Create/select class and subject
-   Create a session, then open and close the attendance window
-   Display the rotating QR code
-   View the live roster of marked, rejected, and flagged students
-   Approve/manage/override attendance
-   Approve student device changes
-   View attendance reports

------------------------------------------------------------------------

## 3. Admin Panel

``` text
Admin Login
     |
     v
Admin Dashboard
     |
     +---- Students
     +---- Teachers
     +---- Departments
     +---- Classes
     +---- Subjects
     +---- Locations
     +---- Attendance Radius (10 m)
     +---- Classroom Networks
     +---- Devices
     +---- Flagged Attempts
     +---- Reports
     +---- Export
```

### Admin Functions

-   Manage students.
-   Manage teachers.
-   Manage departments.
-   Manage subjects.
-   Create college/classroom GPS locations.
-   Configure attendance radius (default 10 m), classroom networks,
    token lifetimes, and window limits.
-   Manage device bindings and review flagged attempts.
-   Generate daily/monthly/student-wise reports.
-   Export attendance to Excel/CSV/PDF.

------------------------------------------------------------------------

# Architecture

The project can follow a simple three-tier architecture:

``` text
+-----------------------------+
|        Client Layer         |
|-----------------------------|
| Student Web/Mobile UI       |
| Teacher Panel               |
| Admin Panel                 |
+--------------+--------------+
               |
               | HTTP/HTTPS
               v
+-----------------------------+
|       Application Layer     |
|-----------------------------|
| Flask Backend               |
| Authentication              |
| Window State Machine        |
| Token Service (rotating QR) |
| Network Verification        |
| Device Binding              |
| Attendance Logic            |
| Geofencing Logic (10 m)     |
| Anomaly Detection           |
| Report Generation           |
+--------------+--------------+
               |
               v
+-----------------------------+
|          Data Layer         |
|-----------------------------|
| SQLite / MySQL              |
| Students                    |
| Teachers                    |
| Classes                     |
| Subjects                    |
| Locations (+ networks)      |
| Attendance Sessions         |
| Devices                     |
| Session Tokens              |
| Attendance Records          |
| Attendance Attempts         |
+-----------------------------+
```

------------------------------------------------------------------------

# Technology Stack

  Component          Technology
  ------------------ ------------------------------
  Frontend           HTML5, CSS3, JavaScript
  Backend            Python Flask
  Database           SQLite / MySQL
  GPS                HTML5 Geolocation API
  Maps               OpenStreetMap / Google Maps
  Authentication     Session-based authentication
  Reports            Python libraries / CSV / PDF
  Development Tool   VS Code
  Version Control    Git/GitHub

The project can initially use SQLite for a simple college mini-project.
MySQL can be used if the application needs multiple users, centralized
deployment, or a production-like environment.

------------------------------------------------------------------------

# Functional Requirements

## Authentication

The system should provide:

-   Student registration/login.
-   Teacher login.
-   Admin login.
-   Password verification.
-   Logout.
-   Role-based access.

## Attendance

The system should:

-   Display sessions only while a teacher has the window open.
-   Refuse every attendance request when no window is open.
-   Issue and rotate one-time QR tokens while the window is open.
-   Request GPS permission.
-   Get current location.
-   Calculate distance from the classroom location.
-   Validate the 10 m geofence with accuracy awareness.
-   Verify the classroom network and the bound device.
-   Prevent duplicate attendance.
-   Prevent one device marking for two students.
-   Store attendance information and log every attempt.
-   Return a clear, specific success/rejection message.

## Teacher Management

Teachers should be able to:

-   Create/select classes.
-   Select subjects.
-   Start attendance sessions.
-   View attendance.
-   Manage attendance records.
-   Generate reports.

## Admin Management

Administrators should be able to:

-   Create/update/delete students.
-   Create/update/delete teachers.
-   Manage departments.
-   Manage classes.
-   Manage subjects.
-   Configure locations.
-   Configure attendance radius (default 10 m), classroom networks,
    token lifetimes, and window limits.
-   Manage device bindings and review flagged attempts.
-   Generate and export reports.

------------------------------------------------------------------------

# Non-Functional Requirements

## Security

-   Passwords should never be stored as plain text.
-   Use password hashing.
-   Validate all incoming data.
-   Use authenticated sessions.
-   Apply role-based authorization.
-   Use HTTPS when deployed.
-   Validate location data on the server.
-   Generate tokens with a cryptographically secure random source.
-   Read device identity from a signed `HttpOnly` cookie, not the body.
-   Rate-limit attendance attempts per student and per device.
-   Enforce uniqueness constraints in the database, not only in code.

## Performance

Attendance verification should normally complete within a few seconds,
depending on GPS acquisition and network conditions.

## Usability

The interface should be simple enough that a student can mark attendance
with minimal interaction.

## Reliability

The system should handle:

-   GPS unavailable.
-   Internet unavailable.
-   Classroom Wi-Fi unavailable (teacher override path).
-   Permission denied.
-   Duplicate attendance.
-   Invalid sessions.
-   Invalid coordinates.
-   Poor GPS accuracy (retry, not rejection).
-   Expired tokens between rotations.
-   A session left open by a crashed process (auto-close on timer).
-   Concurrent duplicate requests (database constraints).

------------------------------------------------------------------------

# GPS and Geofencing

A **geofence** is a virtual geographic boundary around a physical
location.

For example:

``` text
Classroom Location
Latitude  : 28.6139
Longitude : 77.2090

Allowed Radius
10 metres
```

A student located within 10 metres of the configured point is eligible to
continue to the remaining checks.

Conceptually:

``` text
                 College
                    *
               .---------.
            .-'           '-.
          .'                 '.
         /     Allowed        \
        |      Radius          |
        |                      |
         \                    /
          '.                .'
            '-.__________.-'

             Student
                *
```

The radius is configurable by the administrator, and for this system the
configured value is:

``` text
GEOFENCE_RADIUS_METERS = 10
```

### Where the circle is centred

The centre is **wherever the teacher was standing when they opened the
window**, not a coordinate typed in beforehand.

``` text
Teacher presses "Open Attendance"
        |
        v
Teacher's device reports lat/lon/accuracy
        |
        +-- accuracy <= 30 m --> circle centred there   (anchor: TEACHER)
        |
        +-- vague / denied ----> classroom's saved point (anchor: LOCATION)
```

This removes the surveying problem described below: the teacher is
already in the room, so their phone *is* the room. It also means a class
held somewhere unusual — a lab swap, an exam hall, a field session —
needs no configuration at all.

The trade is that the centre now carries its own error. A surveyed point
was assumed exact; a live fix is not, and the two errors compound. Two
phones sitting side by side can differ by the sum of their uncertainties,
so the anchor's accuracy is forgiven on top of the student's:

``` text
credit    = min(student_accuracy, 35) + min(anchor_accuracy, 25)
effective = distance - credit
```

Without that second term, a student sitting next to the teacher gets
rejected for the *teacher's* GPS noise, which is the worst possible
failure mode — it punishes exactly the people who did nothing wrong.

Two guards keep this from loosening the geofence into meaninglessness:

-   **Both credits are capped**, so a hopeless fix cannot buy unlimited
    forgiveness. A student 200 m away is still refused with the most
    generous anchor the system will accept.
-   **An anchor worse than `MAX_ANCHOR_ACCURACY_METERS` (30) is
    refused outright** and the saved coordinates are used instead. A
    circle centred on a bad fix is worse than one centred on a surveyed
    point, because it silently moves the classroom without anybody
    noticing.

The anchor is fixed for the life of the window. `CLOSED` is terminal and
an open window cannot be reopened, so the circle can never move under
students who have already marked.

### Why 10 metres needs more than GPS

A 10-metre circle is roughly the size of one classroom. That is exactly
the intent — but it is smaller than the error of the sensor being used to
measure it:

``` text
Typical smartphone GPS accuracy
-------------------------------------------
Open sky, good conditions      3 -  10 m
Outdoors near buildings        10 -  30 m
Inside a building             30 - 100 m+
```

If the server ran a naive `distance <= 10` test against a raw reading, a
student sitting in the front row could be reported 25 metres away and be
rejected, while the phone next to them reads 3 metres and passes. The
radius would behave like a coin flip.

Two adjustments make a 10-metre geofence workable:

**1. Give the reading credit for its own stated error.** The browser
returns an `accuracy` value — the radius of the 68% confidence circle. If
a reading says "I am 22 m away, ±20 m", the student may well be standing
in the room. The comparison used is therefore:

``` text
effective_distance = distance - min(accuracy, ACCURACY_CREDIT)
effective_distance <= GEOFENCE_RADIUS_METERS
```

with `ACCURACY_CREDIT = 35` and a hard rejection when
`accuracy > MAX_ACCURACY_METERS (50)`. The geofence stays configured at
10 m; it simply stops punishing students for their hardware's noise.

**2. Stop relying on GPS for the anti-proxy guarantee.** Loosening the
comparison would weaken security if GPS were the only check — so it is
not. Presence is actually proven by signals that physically cannot reach
outside the room: a QR token that must be read off the classroom screen
within seconds, and a request that must originate from the classroom
network. GPS confirms the student is at the campus and not in another
city; the short-range layers confirm they are in *this room*.

This is the trade the design makes deliberately: **a strict radius that
is loose about sensor noise, wrapped in layers that are strict about
everything else.** See [Anti-Proxy Design](#anti-proxy-design).

If the classroom has usable GPS reception and testing at the actual
location shows accuracy consistently under 15 m, `ACCURACY_CREDIT` can be
lowered to tighten the geofence further.

------------------------------------------------------------------------

# Distance Calculation

Latitude and longitude are coordinates on the Earth's surface. The
backend can use the **Haversine formula** to calculate the approximate
distance between two GPS coordinates.

For two points:

``` text
Point 1 = (lat1, lon1)
Point 2 = (lat2, lon2)
```

The Haversine formula is:

``` text
a = sin²(Δlat / 2)
    + cos(lat1) × cos(lat2) × sin²(Δlon / 2)

c = 2 × atan2(√a, √(1-a))

distance = R × c
```

where:

``` text
R ≈ 6,371,000 metres
```

The backend then applies the accuracy-aware geofence test:

``` python
RADIUS_METERS   = 10     # the configured geofence
ACCURACY_CREDIT = 35     # max error the reading may be forgiven
MAX_ACCURACY    = 50     # readings worse than this are unusable

def check_geofence(distance, accuracy):
    if accuracy is None or accuracy > MAX_ACCURACY:
        return "RETRY_POOR_ACCURACY"

    effective = distance - min(accuracy, ACCURACY_CREDIT)

    if effective <= RADIUS_METERS:
        return "INSIDE"
    return "OUTSIDE"
```

Worked examples against the 10-metre radius:

``` text
distance  accuracy  effective  result   interpretation
--------------------------------------------------------------------
   4.2 m     8.4 m    -4.2 m   INSIDE   front row, good fix
  28.0 m    24.0 m     4.0 m   INSIDE   in the room, noisy indoor fix
  55.0 m    12.0 m    43.0 m   OUTSIDE  in the corridor/next block
 180.0 m    15.0 m   165.0 m   OUTSIDE  not on this floor
  30.0 m    90.0 m        --   RETRY    reading too vague to use
```

The row that matters is the third one: a student 55 m away is rejected
even with a reasonable fix, because the credit is capped. And the student
in row two, who would have been falsely rejected by a naive test, is
correctly admitted — while still having to pass the token, network, and
device checks before anything is recorded.

### Important GPS Consideration

GPS accuracy varies significantly depending on:

-   Indoor/outdoor location.
-   Device hardware.
-   Weather/environment.
-   Buildings and obstructions.
-   Number of available satellites.
-   Wi-Fi/mobile network assistance.

The practical consequence is stated plainly: **a 10-metre GPS-only check
is not reliable, and this system does not use one.** The 10-metre radius
is enforced as one layer among several, using the accuracy-aware
comparison above. Before deployment, walk the actual classroom with a
test device and record the accuracy values you see — then tune
`ACCURACY_CREDIT` to the real numbers rather than to the defaults here.

------------------------------------------------------------------------

# Teacher-Controlled Attendance Window

**Requirement: a student can mark attendance only once the teacher turns
it on.**

This is enforced as a state machine on the session row, checked on the
server for every single request. It is not a UI convenience.

## Session states

``` text
   [ SCHEDULED ]  teacher created the session, nothing is open
        |
        |  teacher presses "Open Attendance"
        v
   [ ACTIVE ]     opened_at set, closes_at = opened_at + window_seconds
        |         tokens are generated, students may mark
        |
        +--- teacher presses "Close Attendance" ---+
        |                                          |
        +--- closes_at reached (auto-close) -------+
                                                   |
                                                   v
                                            [ CLOSED ]  terminal
```

`CLOSED` is terminal. Reopening requires creating a new session, so a
closed window can never be silently reopened to backfill attendance.

## The server-side gate

Every call to `POST /api/attendance/mark` begins with this check, before
any GPS maths happens:

``` python
session = db.get_session(session_id)

if session is None:
    return reject(404, "SESSION_NOT_FOUND")

if session.status != "ACTIVE":
    return reject(403, "WINDOW_NOT_OPEN")

now = utcnow()
if not (session.opened_at <= now <= session.closes_at):
    auto_close(session)
    return reject(403, "WINDOW_EXPIRED")
```

Three properties follow from this:

1.  **No session open means no attendance is possible for anybody.**
    There is no default-open state and no fallback path.
2.  **Checking `status` alone is not enough.** The timestamp comparison
    is also required, so a session left `ACTIVE` by a crashed process or
    a teacher who forgot to close it still expires on its own.
3.  **The window is short by default** (`window_seconds = 120`). A
    two-minute window means a student who is not already in the room when
    the teacher opens it cannot realistically get there and mark in.

## Why the window length matters

The window is the strongest single anti-proxy control in the system,
because it removes the attacker's time budget. Every remote-marking
scheme — messaging a friend a screenshot, driving toward campus, setting
up a spoofed location — needs more than two minutes of unobserved
preparation. Nothing in the flow is announced in advance: students do not
know when the teacher will press the button.

Recommended values:

``` text
window_seconds = 120   default, ordinary lecture
window_seconds =  60   small class, teacher wants it tight
window_seconds = 300   large hall, slow check-in, maximum
```

Values above 300 seconds should be discouraged in the admin UI — the
longer the window, the weaker the guarantee.

------------------------------------------------------------------------

# Anti-Proxy Design

**Requirement: there should be no chance of proxy attendance.**

An honest statement of what is achievable: no self-service attendance
system can be *mathematically* proof against proxy, because the student's
own phone is the sensor and the student controls the phone. What this
design does is stack independent checks so that defeating them all
requires so much coordination, equipment, and physical presence that
proxy stops being worth attempting — and any attempt leaves evidence in
the log.

The rule the design follows: **every layer must be independently
defeated, and at least one layer cannot be defeated from outside the
room.**

## The layers

``` text
Layer 1  Teacher window       attendance impossible unless open, ~120 s
Layer 2  Rotating QR token    must read the classroom screen, ~30 s life
Layer 3  Classroom network    request must exit via the classroom AP
Layer 4  Device binding       one account, one registered device
Layer 5  Device uniqueness    one device cannot mark two students
Layer 6  GPS geofence         10 m, accuracy-aware
Layer 7  Mock-location check  spoofed fixes rejected/flagged
Layer 8  Attempt logging      every failure recorded and shown to teacher
```

## Layer 2 - Rotating one-time token

The teacher's screen displays a QR code that the server regenerates every
`token_rotation_seconds` (default 30) and accepts for
`token_ttl_seconds` (default 35).

``` text
t=0s    token A displayed   accepted until t=35s
t=30s   token B displayed   accepted until t=65s
t=60s   token C displayed   accepted until t=95s
```

The five-second overlap is deliberate: a student who submits just as the
code rotates should not be punished for the round trip.

Choosing this number is a straight trade. Fifteen seconds is harder to
relay to an absent friend; thirty is comfortably long enough to read six
characters off a screen and type them. Thirty is the default here because
a system that rejects honest students gets switched off, and the token is
not the only thing standing between a remote student and a record — they
still have to be on the classroom network, on their own registered
device.

Each token is a random 32-byte value stored server-side against the
session — never a hash of anything predictable, so it cannot be computed
offline.

What this defeats: **a student photographing the code and sending it to
an absent friend.** By the time the image is sent, opened, and scanned,
the token is dead. Sustaining the attack would require a live video feed
of the screen plus a confederate refreshing continuously — and that
confederate still has to pass layers 3, 4, and 6.

Tokens are only generated while the session is `ACTIVE`. When the window
closes, all outstanding tokens are invalidated immediately.

## Layer 3 - Classroom network verification

The strongest cheap signal available to a *web* application is where the
request came from.

``` python
if request.remote_addr not in session.location.allowed_networks:
    return reject(403, "WRONG_NETWORK")
```

The admin registers the classroom's egress IP (or the campus Wi-Fi NAT
address) against the location. A student sitting at home on mobile data
fails this check no matter how perfect their GPS coordinates are, because
they cannot forge the source address of a TCP connection they need
responses on.

Two caveats to handle honestly:

-   **Students on mobile data inside the classroom will fail this
    check.** That is intended — the policy is "join the classroom Wi-Fi
    to mark attendance". Make this clear to students in advance, and make
    sure the classroom AP is reachable.
-   **A whole campus behind one NAT IP** weakens the check to
    campus-level. Where the network team can expose per-AP information,
    record the Wi-Fi **BSSID** instead — but note that browsers cannot
    read BSSID, so that variant requires the mobile app from
    [Future Scope](#future-scope).

## Layer 4 and 5 - Device binding

On first login a student registers one device. The server stores a signed
device identifier in a long-lived `HttpOnly` cookie and records its
fingerprint.

``` text
Student 101  ->  device d4f9a1...   registered 12-08-2026
```

Two rules follow:

-   A mark request from any other device is rejected
    (`DEVICE_NOT_REGISTERED`), so a friend cannot log in as the absent
    student on their own phone.
-   A single device cannot mark attendance for two different students in
    the same session (`DEVICE_ALREADY_USED`), so handing one unlocked
    phone around the room does not work either.

Changing device requires teacher or admin approval, and every change is
logged. Rate-limit approvals — a student requesting a device reset every
week is a signal worth reviewing.

## Layer 7 - Mock location detection

On Android, `Location.isFromMockProvider()` reveals a spoofed fix; the
mobile app should send this flag and the server must reject when it is
true. A browser cannot access it, so the web client additionally screens
for the signatures of spoofed readings:

-   `accuracy` reported as an implausibly perfect constant (many
    spoofing apps emit a fixed value).
-   Coordinates identical to the classroom point to more decimal places
    than a real fix ever produces.
-   Impossible travel — the same account reporting positions kilometres
    apart within minutes across consecutive sessions.

These are heuristics, not proofs. They should raise a `FLAGGED` status on
the teacher's roster for a human decision, not silently delete a record.

## Layer 8 - Everything is logged

Every attempt — successful, rejected, or flagged — is written to
`attendance_attempts` with the failure reason, coordinates, device, IP,
and timestamp. This turns proxy from an invisible act into a visible one:
a pattern of `WRONG_NETWORK` or `DEVICE_ALREADY_USED` failures is exactly
what a student attempting proxy leaves behind.

## What remains possible

Stated plainly, so the limitation is not discovered later:

-   A student who is physically in the room can mark attendance and then
    leave. No location system detects this; only a mid-class second
    check-in does.
-   A determined attacker with a rooted phone, a live video feed of the
    classroom screen, and a confederate on the classroom Wi-Fi willing to
    tether them could defeat layers 2, 3, and 6 simultaneously. This is a
    conspiracy involving a physically present accomplice — at which point
    the accomplice could simply answer a roll call.
-   The teacher can always override. Human judgement is the final
    authority, and the live roster exists so that judgement is informed.

The realistic claim this system supports is: **casual proxy attendance is
prevented, and serious attempts require in-room collaboration and leave
an audit trail.** That is a much stronger and more defensible statement
than "GPS makes proxy impossible", which is not true of any GPS system.

------------------------------------------------------------------------

# Database Design

The database can contain the following major entities:

``` text
Student
   |
   | 1:N
   v
Attendance
   ^
   |
   | N:1
Attendance Session
   |
   +---- Class
   |
   +---- Subject
   |
   +---- Teacher
   |
   +---- Location
```

Additional tables can include:

-   Departments
-   Classes
-   Subjects
-   Teachers
-   Locations
-   Attendance Sessions
-   Attendance Records

------------------------------------------------------------------------

# Suggested Database Schema

## Students

  Field           Type       Description
  --------------- ---------- ---------------------
  id              INTEGER    Primary key
  name            VARCHAR    Student name
  roll_no         VARCHAR    College roll number
  email           VARCHAR    Student email
  password_hash   VARCHAR    Hashed password
  department_id   INTEGER    Department
  class_id        INTEGER    Class
  created_at      DATETIME   Registration time

------------------------------------------------------------------------

## Teachers

  Field           Type       Description
  --------------- ---------- -----------------
  id              INTEGER    Primary key
  name            VARCHAR    Teacher name
  email           VARCHAR    Teacher email
  password_hash   VARCHAR    Hashed password
  department_id   INTEGER    Department
  created_at      DATETIME   Creation time

------------------------------------------------------------------------

## Departments

  Field   Type      Description
  ------- --------- -----------------
  id      INTEGER   Primary key
  name    VARCHAR   Department name

Example:

``` text
Computer Science
Information Technology
Electronics
Mechanical
Civil
```

------------------------------------------------------------------------

## Classes

  Field           Type      Description
  --------------- --------- ---------------
  id              INTEGER   Primary key
  name            VARCHAR   Class name
  department_id   INTEGER   Department
  year            INTEGER   Academic year
  section         VARCHAR   Section

------------------------------------------------------------------------

## Subjects

  Field           Type      Description
  --------------- --------- --------------
  id              INTEGER   Primary key
  name            VARCHAR   Subject name
  code            VARCHAR   Subject code
  department_id   INTEGER   Department

------------------------------------------------------------------------

## Locations

  Field              Type      Description
  ------------------ --------- ---------------------------------------
  id                 INTEGER   Primary key
  name               VARCHAR   Location name
  latitude           DECIMAL   Latitude (6+ decimal places)
  longitude          DECIMAL   Longitude (6+ decimal places)
  radius_meters      INTEGER   Allowed radius, default 10
  allowed_networks   VARCHAR   Comma-separated egress IPs/CIDRs
  wifi_bssid         VARCHAR   Classroom AP BSSID (mobile app only)

Store latitude/longitude with at least 6 decimal places. At 5 decimals a
single unit is about 1.1 m, which is already a tenth of the radius —
rounding to 4 decimals would move the classroom centre by up to 11 m and
break the geofence on its own.

Example:

``` text
Name: CS Block - Room 204
Latitude: 28.613900
Longitude: 77.209000
Radius: 10
Allowed networks: 203.0.113.44
```

------------------------------------------------------------------------

## Attendance Sessions

  Field                    Type       Description
  ------------------------ ---------- ---------------------------------
  id                       INTEGER    Primary key
  teacher_id               INTEGER    Teacher
  class_id                 INTEGER    Class
  subject_id               INTEGER    Subject
  location_id              INTEGER    Authorized location
  start_time               DATETIME   Scheduled session start
  end_time                 DATETIME   Scheduled session end
  status                   VARCHAR    SCHEDULED/ACTIVE/CLOSED
  opened_at                DATETIME   When the teacher opened the window
  closes_at                DATETIME   Auto-close deadline
  closed_at                DATETIME   When it actually closed
  window_seconds           INTEGER    Window length, default 120
  token_rotation_seconds   INTEGER    QR refresh interval, default 30
  token_ttl_seconds        INTEGER    Token lifetime, default 35
  anchor_latitude          DECIMAL    Geofence centre, from the teacher
  anchor_longitude         DECIMAL    Geofence centre, from the teacher
  anchor_accuracy          DECIMAL    Error of that fix, forgiven later
  anchor_source            VARCHAR    TEACHER / LOCATION

`opened_at` and `closes_at` are NULL while the session is `SCHEDULED`.
The attendance endpoint requires both to be set and `now` to fall
between them.

------------------------------------------------------------------------

## Devices

  Field           Type       Description
  --------------- ---------- -----------------------------------
  id              INTEGER    Primary key
  student_id      INTEGER    Owning student
  device_hash     VARCHAR    Signed device identifier (unique)
  fingerprint     VARCHAR    UA/platform fingerprint
  status          VARCHAR    ACTIVE/REVOKED/PENDING_APPROVAL
  registered_at   DATETIME   First registration
  approved_by     INTEGER    Teacher/admin who approved a change

A unique constraint on `device_hash` enforces one account per device.

------------------------------------------------------------------------

## Session Tokens

  Field        Type       Description
  ------------ ---------- ------------------------------
  id           INTEGER    Primary key
  session_id   INTEGER    Owning session
  token        VARCHAR    Random 32-byte value (unique)
  issued_at    DATETIME   Generation time
  expires_at   DATETIME   issued_at + token_ttl_seconds

Tokens are generated only while the session is `ACTIVE`. Expired rows can
be purged after the session closes.

------------------------------------------------------------------------

## Attendance

  Field               Type      Description
  ------------------- --------- ------------------------------------
  id                  INTEGER   Primary key
  student_id          INTEGER   Student
  session_id          INTEGER   Attendance session
  date                DATE      Attendance date
  time                TIME      Attendance time
  latitude            DECIMAL   Student latitude
  longitude           DECIMAL   Student longitude
  accuracy            DECIMAL   GPS accuracy
  distance_meters     DECIMAL   Raw calculated distance
  effective_meters    DECIMAL   Distance after accuracy credit
  device_id           INTEGER   Device used
  token_id            INTEGER   Token redeemed
  source_ip           VARCHAR   Request source address
  verification_flags  VARCHAR   Which layers passed
  status              VARCHAR   PRESENT/FLAGGED/REJECTED

Two unique constraints are required:

``` text
(student_id, session_id)   one record per student per session
(device_id,  session_id)   one device cannot mark two students
```

The first prevents duplicate attendance. The second is the anti-proxy
constraint — it is what stops a single phone being passed around the
room, and it belongs in the database rather than only in application
code so that a race between two concurrent requests cannot slip past it.

------------------------------------------------------------------------

## Attendance Attempts

Every attempt is logged, not just the successful ones.

  Field            Type       Description
  ---------------- ---------- ------------------------------------
  id               INTEGER    Primary key
  student_id       INTEGER    Student who attempted
  session_id       INTEGER    Target session
  attempted_at     DATETIME   Timestamp
  result           VARCHAR    ACCEPTED/REJECTED/FLAGGED
  failure_reason   VARCHAR    WINDOW_NOT_OPEN, TOKEN_EXPIRED, ...
  latitude         DECIMAL    Reported latitude
  longitude        DECIMAL    Reported longitude
  accuracy         DECIMAL    Reported accuracy
  distance_meters  DECIMAL    Calculated distance
  device_hash      VARCHAR    Device presented
  source_ip        VARCHAR    Request source address

This table is what makes proxy attempts visible. It is also the most
privacy-sensitive table in the system — see
[Privacy Considerations](#privacy-considerations) for retention.

------------------------------------------------------------------------

# Application Modules

## Module 1 - Authentication

Responsibilities:

-   Registration.
-   Login.
-   Logout.
-   Password hashing.
-   Role management.
-   Session management.

Roles:

``` text
STUDENT
TEACHER
ADMIN
```

------------------------------------------------------------------------

## Module 2 - Student Management

Admin can:

-   Add student.
-   Update student.
-   Delete/deactivate student.
-   Assign department.
-   Assign class.
-   View student details.

------------------------------------------------------------------------

## Module 3 - Teacher Management

Admin can:

-   Add teacher.
-   Update teacher.
-   Assign department.
-   Manage teacher account.

------------------------------------------------------------------------

## Module 4 - Subject Management

Admin can:

-   Create subject.
-   Update subject.
-   Assign subject to department/class.

------------------------------------------------------------------------

## Module 5 - Location Management

Admin can configure:

``` text
Location Name
Latitude          (6+ decimal places)
Longitude         (6+ decimal places)
Allowed Radius    (default 10 metres)
Allowed Networks  (classroom egress IP/CIDR)
```

Because the radius is 10 m, the coordinates must be captured *inside the
room they describe* — reading them off a map pin is not accurate enough.
Stand in the centre of the classroom, take several readings with a test
device, and use the average.

Example:

``` text
Location: CS Block - Room 204
Latitude: 28.613900
Longitude: 77.209000
Radius: 10 metres
Allowed networks: 203.0.113.44
```

------------------------------------------------------------------------

## Module 6 - Attendance Session

A teacher creates a session, then explicitly opens the attendance window.
These are two separate actions, and only the second one lets students
mark in.

``` text
Teacher : Mr. Sharma
Class   : CSE 3A
Subject : Database Management
Location: CS Block - Room 204

Status  : SCHEDULED      <-- students cannot mark
          [ Open Attendance ]
```

After opening:

``` text
Status     : ACTIVE
Opened at  : 11:24:30
Closes at  : 11:26:30
Marked     : 41 / 62
Rejected   : 3
Flagged    : 1

          [ Close Attendance ]
```

Only students belonging to the session's class may participate. The full
state machine is described in
[Teacher-Controlled Attendance Window](#teacher-controlled-attendance-window).

------------------------------------------------------------------------

## Module 7 - Verification Chain

The client provides:

``` text
session_id
token          (scanned from the teacher's QR code)
latitude
longitude
accuracy
device_hash    (from the signed cookie)
```

The backend evaluates each layer in order and stops at the first failure.
GPS is deliberately checked late — the cheap, unspoofable checks run
first.

``` text
Request
   |
   v
Window OPEN and unexpired? ------- no --> reject WINDOW_NOT_OPEN
   |
   v
Token valid and unexpired? ------- no --> reject TOKEN_EXPIRED
   |
   v
Source IP on classroom net? ------ no --> reject WRONG_NETWORK
   |
   v
Device bound to this student? ---- no --> reject DEVICE_NOT_REGISTERED
   |
   v
Device unused this session? ------ no --> reject DEVICE_ALREADY_USED
   |
   v
Student enrolled in class? ------- no --> reject NOT_ENROLLED
   |
   v
Coordinates valid, not mocked? --- no --> reject INVALID_LOCATION
   |
   v
accuracy <= 50 m? ---------------- no --> retry  POOR_ACCURACY
   |
   v
effective distance <= 10 m? ------ no --> reject OUTSIDE_RADIUS
   |
   v
Not already marked? -------------- no --> reject ALREADY_MARKED
   |
   v
Record attendance  -->  PRESENT
```

Every reject branch also writes a row to `attendance_attempts`.

------------------------------------------------------------------------

## Module 8 - Attendance History

Students can see:

``` text
Date        Subject             Status
-----------------------------------------
15-08-2026  Data Structures     Present
16-08-2026  DBMS                Present
17-08-2026  Operating Systems   Absent
```

------------------------------------------------------------------------

## Module 9 - Reports

The system can generate:

-   Daily attendance.
-   Monthly attendance.
-   Student-wise attendance.
-   Subject-wise attendance.
-   Class-wise attendance.
-   Teacher-wise session reports.

------------------------------------------------------------------------

# Teacher Workflow

``` text
Login
  |
  v
Select Class
  |
  v
Select Subject
  |
  v
Select Location
  |
  v
Create Session          (status: SCHEDULED - nobody can mark)
  |
  v
Press "Open Attendance" (status: ACTIVE - the gate opens)
  |
  v
Display Rotating QR Code on Classroom Screen
  |
  v
Students Mark Attendance (window_seconds countdown)
  |
  v
Teacher Views Live Roster
  |
  +---- Marked / Rejected / Flagged
  |
  +---- Manual Override where needed
  |
  v
Close Session           (auto or manual - CLOSED is terminal)
  |
  v
Generate Report
```

------------------------------------------------------------------------

# Student Workflow

``` text
Login (registered device)
  |
  v
Dashboard
  |
  v
Is a window open?
  |
  +---- No ---> "Your teacher has not started attendance yet"
  |
 Yes
  |
  v
Press "Scan QR & Mark Attendance"
  |
  v
Scan Teacher's Rotating QR Code
  |
  v
Request GPS Permission
  |
  v
Get Coordinates + Accuracy
  |
  v
Send token + coordinates to Server
  |
  v
Server Runs the Verification Chain
  |
  +-------------------------+
  |                         |
All layers pass       Any layer fails
  |                         |
  v                         v
Check Duplicate       Reject with reason
  |                         |
  v                         v
Save Attendance       Log attempt
  |                         |
  v                         v
Show Success          Show what to fix
```

------------------------------------------------------------------------

# Admin Workflow

``` text
Admin Login
    |
    v
Dashboard
    |
    +---- Manage Students
    |
    +---- Manage Teachers
    |
    +---- Manage Departments
    |
    +---- Manage Classes
    |
    +---- Manage Subjects
    |
    +---- Manage Locations
    |
    +---- Configure Radius (10 m) & Networks
    |
    +---- Manage Devices
    |
    +---- Review Flagged Attempts
    |
    +---- Generate Reports
    |
    +---- Export Reports
```

------------------------------------------------------------------------

# API Design

A Flask REST API can be organized approximately as follows.

## Authentication

### Register Student

``` http
POST /api/auth/register
```

Example request:

``` json
{
  "name": "Gaurav Roy",
  "roll_no": "101",
  "email": "gaurav@example.com",
  "password": "password"
}
```

### Login

``` http
POST /api/auth/login
```

------------------------------------------------------------------------

## Student APIs

### Get Dashboard

``` http
GET /api/student/dashboard
```

### Get Open Sessions

``` http
GET /api/student/sessions
```

Returns only sessions whose window is currently `ACTIVE` and unexpired,
with the seconds remaining. Returns an empty list when no teacher has
opened attendance — the student UI has nothing to press.

### Mark Attendance

``` http
POST /api/attendance/mark
```

Example request:

``` json
{
  "session_id": 12,
  "token": "b7f3c1a9e42d8f06...",
  "latitude": 28.613935,
  "longitude": 77.209021,
  "accuracy": 8.4
}
```

The device identifier is *not* in the body — it is read from the signed
`HttpOnly` cookie so the client cannot choose it.

Successful response:

``` json
{
  "success": true,
  "message": "Attendance marked successfully",
  "distance_meters": 4.2,
  "effective_meters": 0.0,
  "allowed_radius": 10,
  "status": "PRESENT"
}
```

Rejection — window not open (the teacher gate):

``` json
{
  "success": false,
  "error": "WINDOW_NOT_OPEN",
  "message": "Your teacher has not opened attendance for this session."
}
```

Rejection — outside the geofence:

``` json
{
  "success": false,
  "error": "OUTSIDE_RADIUS",
  "message": "You are outside the classroom attendance area",
  "distance_meters": 183.7,
  "effective_meters": 168.7,
  "allowed_radius": 10
}
```

Rejection — anti-proxy layers:

``` json
{
  "success": false,
  "error": "DEVICE_ALREADY_USED",
  "message": "This device has already marked attendance for another
              student in this session."
}
```

Error codes returned by this endpoint:

``` text
WINDOW_NOT_OPEN         teacher has not opened attendance
WINDOW_EXPIRED          the window closed before the request arrived
TOKEN_MISSING           no QR token supplied
TOKEN_EXPIRED           token older than token_ttl_seconds
TOKEN_INVALID           token not issued by this session
WRONG_NETWORK           request did not come from the classroom network
DEVICE_NOT_REGISTERED   device is not bound to this account
DEVICE_ALREADY_USED     device already marked for another student
NOT_ENROLLED            student is not in this session's class
INVALID_LOCATION        malformed or mock coordinates
POOR_ACCURACY           accuracy worse than MAX_ACCURACY_METERS
OUTSIDE_RADIUS          effective distance exceeds the 10 m geofence
ALREADY_MARKED          duplicate attendance for this session
```

------------------------------------------------------------------------

## Device Registration

``` http
POST /api/student/device/register
POST /api/student/device/change-request
```

The first call binds the account to the device it is made from. The
second raises a request that a teacher or admin must approve.

------------------------------------------------------------------------

## Attendance History

``` http
GET /api/student/attendance
```

------------------------------------------------------------------------

## Teacher APIs

### Create Session

``` http
POST /api/teacher/sessions
```

Creates the session in `SCHEDULED` state. No student can mark attendance
yet.

### Open the Attendance Window

``` http
POST /api/teacher/sessions/<session_id>/open
```

Request — the teacher's own position centres the geofence:

``` json
{
  "window_seconds": 120,
  "latitude": 28.615700,
  "longitude": 77.210500,
  "accuracy": 9.0
}
```

Send `"anchor": false` to skip it and use the classroom's saved
coordinates instead.

Response:

``` json
{
  "status": "ACTIVE",
  "opened_at": "2026-08-17T11:24:30Z",
  "closes_at": "2026-08-17T11:26:30Z",
  "anchor": {
    "source": "TEACHER",
    "latitude": 28.6157,
    "longitude": 77.2105,
    "accuracy": 9.0,
    "radius_meters": 10,
    "note": null
  }
}
```

When the fix is missing or too vague, `source` comes back as `LOCATION`
and `note` says why in plain language.

This is the switch the whole system hangs on. Only the teacher who owns
the session (or an admin) may call it.

### Get the Current QR Token

``` http
GET /api/teacher/sessions/<session_id>/token
```

Returns the token currently displayed, refreshed by the teacher's screen
every `token_rotation_seconds`. Returns `403 WINDOW_NOT_OPEN` when the
session is not `ACTIVE`.

### View Session Attendance (live roster)

``` http
GET /api/teacher/sessions/<session_id>/attendance
```

Returns marked students plus rejected and flagged attempts, so the
teacher can see proxy attempts as they happen.

### Close the Attendance Window

``` http
POST /api/teacher/sessions/<session_id>/close
```

Moves the session to `CLOSED` and invalidates all outstanding tokens.
`CLOSED` is terminal.

### Override an Attendance Record

``` http
POST /api/teacher/sessions/<session_id>/override
```

Lets the teacher mark a student present or absent manually — for the
student whose phone died, or the flagged record they have judged
legitimate. Every override is logged with the acting teacher's id.

------------------------------------------------------------------------

## Admin APIs

``` http
GET    /api/admin/students
POST   /api/admin/students
PUT    /api/admin/students/<id>
DELETE /api/admin/students/<id>

GET    /api/admin/teachers
POST   /api/admin/teachers

GET    /api/admin/locations
POST   /api/admin/locations
PUT    /api/admin/locations/<id>

GET    /api/admin/reports/daily
GET    /api/admin/reports/monthly
GET    /api/admin/reports/student/<id>
```

The exact API structure can be adjusted according to the implementation.

------------------------------------------------------------------------

# Project Structure

The implemented structure:

``` text
Attendence/
│
├── app.py                    # application factory, CLI, error handlers
├── config.py                 # every tunable, with its security note
├── extensions.py             # db instance
├── util.py                   # utcnow()
├── seed.py                   # demo data
├── requirements.txt
├── requirements-dev.txt      # adds pytest
├── pytest.ini
├── .env.example
├── .gitignore
│
├── models/
│   ├── __init__.py           # re-exports so create_all sees everything
│   ├── academic.py           # Department, ClassGroup, Subject
│   ├── people.py             # Student, Teacher, Admin + password hashing
│   ├── location.py           # classroom + allowed_networks
│   ├── session.py            # AttendanceSession state machine, SessionToken
│   ├── device.py             # Device, DeviceChangeRequest
│   └── attendance.py         # Attendance, AttendanceAttempt
│
├── routes/
│   ├── helpers.py            # source IP, device cookie, payload parsing
│   ├── auth.py               # register, login, logout
│   ├── attendance.py         # POST /api/attendance/mark
│   ├── student.py            # sessions, device registration, history
│   ├── teacher.py            # open/close window, token, QR, roster, override
│   ├── admin.py              # users, locations, devices, attempts, reports
│   └── pages.py              # server-rendered pages
│
├── services/
│   ├── geolocation.py        # haversine + accuracy-aware geofence
│   ├── window_service.py     # SCHEDULED -> ACTIVE -> CLOSED
│   ├── token_service.py      # rotating token generation and validation
│   ├── device_service.py     # binding, uniqueness, change approval
│   ├── network_service.py    # classroom network verification
│   ├── anomaly_service.py    # mock-location and impossible travel
│   ├── attendance_service.py # THE VERIFICATION CHAIN
│   ├── auth_service.py       # sessions and role_required
│   └── report_service.py     # reports and CSV export
│
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── student/{dashboard,attendance,history}.html
│   ├── teacher/{dashboard,session}.html
│   └── admin/{dashboard,locations,attempts}.html
│
├── static/
│   ├── css/style.css
│   └── js/{attendance,dashboard,teacher_session,
│           teacher_dashboard,admin,admin_locations,admin_attempts}.js
│
└── tests/
    ├── conftest.py
    ├── test_geolocation.py   # the geofence maths
    ├── test_window.py        # the teacher gate (TG01-TG09)
    └── test_antiproxy.py     # the anti-proxy layers (AP01-AP16)
```

The single most important file is
[`services/attendance_service.py`](services/attendance_service.py): it is
the verification chain, and every rule in
[Attendance Validation Rules](#attendance-validation-rules) is enforced
there in order.

------------------------------------------------------------------------

# Installation and Setup

## Prerequisites

-   Python 3.10 or newer (developed and tested on 3.14)
-   pip
-   A modern browser with geolocation support

SQLite is used by default and needs no installation.

------------------------------------------------------------------------

## Create Virtual Environment

### Windows

``` bash
python -m venv venv
venv\Scripts\activate
```

### Linux/macOS

``` bash
python3 -m venv venv
source venv/bin/activate
```

------------------------------------------------------------------------

## Install Dependencies

``` bash
pip install -r requirements.txt
```

`requirements.txt` contains:

``` text
Flask>=3.0
Flask-SQLAlchemy>=3.1
SQLAlchemy>=2.0
Werkzeug>=3.0
python-dotenv>=1.0
qrcode[pil]>=7.4
```

`qrcode` is the only optional one. Without it the teacher panel falls
back to the short typed code and everything still works.

For the test suite:

``` bash
pip install -r requirements-dev.txt
```

------------------------------------------------------------------------

## Load Demo Data

``` bash
python seed.py
```

This creates the database and a working demo college:

``` text
Admin    admin@college.edu    / password123
Teacher  sharma@college.edu   / password123
Students 101@college.edu .. 105@college.edu / password123

Classroom: CS Block - Room 204
           28.613900, 77.209000, 10 m radius
```

The seeded classroom allows loopback and private-LAN addresses so the
network layer passes while you are testing on your own machine or a phone
on the same Wi-Fi. A real classroom would list only its own egress
address.

------------------------------------------------------------------------

# Configuration

Create a `.env` file:

``` env
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///attendance.db

# --- Geofence ---
GEOFENCE_RADIUS_METERS=10
ACCURACY_CREDIT_METERS=35
MAX_ACCURACY_METERS=50

# --- Teacher-controlled window ---
DEFAULT_WINDOW_SECONDS=120
MAX_WINDOW_SECONDS=300

# --- Rotating QR token ---
TOKEN_ROTATION_SECONDS=30
TOKEN_TTL_SECONDS=35

# --- Anti-proxy ---
ENFORCE_NETWORK_CHECK=true
ENFORCE_DEVICE_BINDING=true
DEVICE_COOKIE_NAME=att_device
```

Every one of these has a security consequence. In particular, raising
`MAX_WINDOW_SECONDS` or disabling `ENFORCE_NETWORK_CHECK` /
`ENFORCE_DEVICE_BINDING` materially weakens the anti-proxy guarantee —
they exist for local development and should be `true` in any real
deployment.

For MySQL:

``` env
DATABASE_URL=mysql+pymysql://username:password@localhost/attendance
```

Do not commit real credentials to GitHub.

Add `.env` to `.gitignore`:

``` text
.env
venv/
__pycache__/
*.pyc
attendance.db
```

------------------------------------------------------------------------

# Running the Project

Start the Flask server:

``` bash
python app.py
```

Then open:

``` text
http://127.0.0.1:5000
```

## Walking through it

1.  Log in as **sharma@college.edu** (Teacher). Create a session for
    CSE 3A / Data Structures / CS Block - Room 204.
2.  On the session page, note that the status is `SCHEDULED` and there is
    no QR code. Nothing a student does can produce attendance yet.
3.  In another browser (or a private window), log in as
    **101@college.edu** and register the device. The dashboard says the
    teacher has not opened attendance.
4.  Back on the teacher page, leave **"Centre the 10 m circle on where I
    am standing"** ticked and press **Open Attendance**. The browser reads
    the teacher's position, the circle is centred there, and the QR code,
    six-character code and countdown appear. The confirmation line tells
    you exactly where the circle landed and how accurate the fix was.
5.  The student dashboard picks the session up within a few seconds.
    Open it, scan the QR — or type the six-character code — and allow
    location access.
6.  The roster on the teacher page fills in, and refused attempts appear
    underneath with their reason.

Because the circle follows the teacher, both browsers reporting roughly
the same position is all it takes — you no longer have to move the
seeded classroom to wherever you are.

## Testing on a real phone

Two things bite here, both worth knowing before you demo:

-   **Browser geolocation requires a secure context.** `localhost` is
    exempt, but a phone hitting `http://192.168.x.x:5000` is not, and the
    browser will silently refuse to provide a position. Serve over HTTPS
    (a self-signed certificate or a tunnel such as `ngrok` is enough for
    testing), or test the geofence from the machine itself.
-   **QR scanning uses the `BarcodeDetector` API**, which Chrome and Edge
    on Android support and Safari on iOS does not. The six-character
    typed code is the fallback and works everywhere — this is why it
    exists.

## Running the tests

``` bash
pytest -q
```

79 tests covering the geofence maths, the teacher gate (TG01-TG09) and
the anti-proxy layers (AP01-AP16).

## Useful commands

``` bash
flask --app app init-db          # create tables only
flask --app app seed             # load demo data
flask --app app upgrade-db       # add columns added after your db was made
flask --app app expire-windows   # close any overdue session
```

`upgrade-db` is idempotent — run it after pulling changes and it adds
only what is missing. A production system would use Alembic; this exists
so a demo database survives a schema change instead of being deleted.

`expire-windows` is a safety net, not a requirement: sessions auto-close
when read after their deadline. Running it on a cron keeps a session
tidy even if nobody looks at it.

------------------------------------------------------------------------

# Example Attendance Result

``` text
========================================
        GPS SELF ATTENDANCE
========================================

Student Name : Gaurav Roy
Roll Number  : 101

Subject      : Data Structures
Teacher      : Mr. Sharma

Current Location:
Latitude  : 28.613935
Longitude : 77.209021
Accuracy  : 8.4 metres

Classroom Location:
Latitude  : 28.613900
Longitude : 77.209000

Distance From Classroom : 4.2 metres
Allowed Radius          : 10 metres

----------------------------------------
Verification
----------------------------------------
✓ Attendance window open (86 s left)
✓ QR token valid
✓ Classroom network
✓ Registered device
✓ Inside the 10 m radius
✓ No duplicate record
----------------------------------------
✓ Attendance marked successfully.
----------------------------------------

Date   : 17-08-2026
Time   : 11:25 AM
Status : PRESENT
```

A rejected attempt shows the student exactly which layer failed:

``` text
----------------------------------------
✗ Attendance could not be marked.
----------------------------------------
✓ Attendance window open (54 s left)
✓ QR token valid
✗ You are not connected to the classroom
  Wi-Fi network.

Connect to "CS-Block-204" and try again.
----------------------------------------
```

------------------------------------------------------------------------

# Attendance Validation Rules

The backend validates attendance using eleven conditions, evaluated in
this order. All of them are mandatory — none is optional, because the
security of the system comes from their combination rather than from any
one of them.

## Rule 1 - Authentication

The student must be logged in.

``` text
Not logged in -> Reject
Logged in -> Continue
```

## Rule 2 - Teacher-Opened Window

The session must be `ACTIVE` **and** the current time must fall between
`opened_at` and `closes_at`.

``` text
status != ACTIVE          -> Reject WINDOW_NOT_OPEN
now outside the window    -> Auto-close, reject WINDOW_EXPIRED
status ACTIVE and in time -> Continue
```

This is the rule that implements "a student can mark attendance only
once the teacher turns it on". Checking `status` without the timestamps
is not sufficient — see
[Teacher-Controlled Attendance Window](#teacher-controlled-attendance-window).

## Rule 3 - Rotating Token

The token scanned from the teacher's QR code must exist, belong to this
session, and not have expired.

``` text
No token / unknown / expired -> Reject
Valid token -> Continue
```

## Rule 4 - Classroom Network

The request must originate from a network registered against the
session's location.

``` text
source IP not in allowed_networks -> Reject WRONG_NETWORK
source IP allowed -> Continue
```

## Rule 5 - Device Binding

The device must be the one registered to this student.

``` text
Unregistered / revoked device -> Reject
Bound device -> Continue
```

## Rule 6 - Device Uniqueness

The device must not have already marked attendance for a different
student in this session.

``` text
Device already used this session -> Reject DEVICE_ALREADY_USED
Device unused -> Continue
```

## Rule 7 - Student Enrollment

The student must belong to the class associated with the session.

``` text
Wrong class -> Reject
Correct class -> Continue
```

## Rule 8 - GPS Availability and Sanity

Valid latitude and longitude must be received, within range, and not
carrying a mock-provider flag.

``` text
No GPS / out of range / mocked -> Reject
Valid GPS -> Continue
```

## Rule 9 - GPS Accuracy

Readings too vague to be meaningful against a 10 m radius are refused
with a retry prompt rather than a rejection.

``` text
accuracy > MAX_ACCURACY_METERS (50) -> Ask user to retry
accuracy <= 50 -> Continue
```

Test this threshold at the actual classroom rather than trusting the
default.

## Rule 10 - Geofence

Calculate the distance between the student and the classroom location,
then apply the accuracy credit.

``` text
effective = distance - min(accuracy, ACCURACY_CREDIT)

effective <= 10 -> Continue
effective >  10 -> Reject OUTSIDE_RADIUS
```

## Rule 11 - Duplicate Prevention

Check whether the student already has an attendance record for the
session.

``` text
Already marked -> Reject duplicate
Not marked -> Record attendance
```

Enforce this with a database unique constraint on
`(student_id, session_id)`, not only in application code — two requests
arriving simultaneously can both pass an application-level check.

------------------------------------------------------------------------

# Security Considerations

GPS verification is a location check, not a perfect anti-cheating
mechanism. The anti-proxy strength of this system comes from the layered
design in [Anti-Proxy Design](#anti-proxy-design), not from GPS.

Important security practices include:

### Server-Side Verification

Do not trust a distance value calculated only by JavaScript.

The client should send coordinates, but the **server should calculate
the final distance** using the authorized location stored in the
database.

The same principle applies to every layer. In particular:

-   The **device identifier** comes from a signed `HttpOnly` cookie the
    client cannot read or edit, never from a value posted in the request
    body.
-   The **source IP** is taken from the connection, never from an
    `X-Forwarded-For` header unless the app is behind a proxy you control
    and you have configured a trusted-proxy list. An unvalidated
    forwarded header lets any student claim to be on the classroom
    network.
-   The **token** is verified against server-side storage, not decoded
    from a self-describing client value.
-   The **window state** is read from the database at request time, not
    inferred from anything the client sends.

### Rate Limiting

Cap attempts per student per session (for example 10) and per device per
minute. Without this, a student can brute-force the token space or retry
a spoofed location until GPS noise lets one through.

### Token Handling

Generate tokens with `secrets.token_urlsafe(32)`, never with a
timestamp, counter, or session id as the seed — a predictable token can
be computed by an absent student who knows when the class started.
Compare tokens with a constant-time comparison.

### Password Security

Never store passwords directly.

Use a password hashing algorithm such as Werkzeug's password hashing
utilities.

### Authorization

Students should not be able to access teacher/admin endpoints.

Example:

``` text
Student -> Student APIs only
Teacher -> Teacher APIs
Admin -> Admin APIs
```

### HTTPS

Use HTTPS in real deployment so credentials and location data are
encrypted in transit.

### Input Validation

Validate:

-   Latitude range: `-90 to 90`
-   Longitude range: `-180 to 180`
-   Accuracy: positive, and rejected above `MAX_ACCURACY_METERS`
-   Session ID
-   Student ID
-   Token format and length
-   Attendance status
-   Radius values
-   `window_seconds` clamped to `MAX_WINDOW_SECONDS`

### Audit Information

Attendance records include:

``` text
created_at
student_id
session_id
latitude
longitude
accuracy
distance_meters
effective_meters
device_id
token_id
source_ip
verification_flags
status
```

And every *attempt*, successful or not, is written to
`attendance_attempts` with its failure reason. This is what lets an
administrator answer "did anyone try to mark attendance from outside?"
rather than only "who is present?".

------------------------------------------------------------------------

# Privacy Considerations

Location data is sensitive information. The application should collect
only what is necessary for attendance verification.

Recommended practices:

-   Explain why location permission is required.
-   Collect location only during attendance check-in unless continuous
    tracking is explicitly required.
-   Do not continuously track students unnecessarily.
-   Restrict access to attendance/location records.
-   Keep location data only for the required retention period.
-   Do not expose student coordinates publicly.
-   Provide appropriate institutional privacy notices.

## Privacy cost of the anti-proxy layers

The measures that make proxy impractical also collect more personal data,
and that trade should be made consciously rather than by accident:

-   **`attendance_attempts` records where students were when they
    failed** — including students who simply had bad Wi-Fi. This is the
    most sensitive table in the system. Give it the shortest retention of
    anything here (30-60 days is usually enough to investigate a
    dispute), and restrict it to the teacher of that class and admins.
-   **Device binding is a persistent identifier** tied to a named
    student. Store a hash, never a raw hardware id, and delete bindings
    when the student leaves.
-   **Source IP is a location signal in itself.** Keep it only as long as
    the attendance record needs to be auditable.
-   **Aggregate attendance is not a location history.** Reports should
    expose presence and percentages; coordinates belong only in the audit
    view, behind an explicit permission.

State the retention periods in the institutional privacy notice, and
purge on schedule rather than keeping everything indefinitely. A system
built to prevent proxy should not quietly become a movement log.

The project is intended for attendance verification and should not be
turned into a general-purpose student tracking system.

------------------------------------------------------------------------

# Advantages

## 1. Reduces Manual Work

Teachers do not need to manually record every student's attendance.

## 2. Saves Classroom Time

Students can mark attendance quickly using their phones.

## 3. Location Verification

Attendance is restricted to a 10-metre radius around the classroom, and
backed by token, network, and device checks so that location alone cannot
be faked into a record.

## 4. Digital Records

All attendance information is stored digitally.

## 5. Easy Reporting

Reports can be generated automatically.

## 6. Duplicate Prevention

A student cannot repeatedly mark attendance for the same session when
the database enforces session-level uniqueness.

## 7. Scalable

The system can be expanded from a mini-project into a larger college
attendance platform.

------------------------------------------------------------------------

# Limitations

GPS-based attendance is useful but has limitations.

## GPS Accuracy

GPS may not always provide exact coordinates, especially indoors.

## Location Spoofing

A sophisticated user may manipulate device location, and a browser cannot
detect it. This is why GPS is not the anti-proxy mechanism here: a
spoofed location still has to arrive with a live token, from the
classroom network, on a bound device.

## Internet Dependency

The student needs network connectivity to send the location to the
backend — and specifically needs to be on the classroom network, which is
a stricter requirement than plain connectivity.

## Classroom Wi-Fi Dependency

If the classroom access point is down or saturated, students cannot mark
attendance at all. Have a fallback: the teacher's manual override exists
for exactly this, and a note in the roster records why it was used.

## Battery Usage

Repeated location requests can consume battery.

## Indoor Locations

GPS accuracy decreases inside buildings, which is why the accuracy credit
in [Distance Calculation](#distance-calculation) exists. In a basement or
a heavily shielded lab, GPS may return nothing usable — in that case the
geofence layer contributes nothing and the token plus network layers are
carrying the check on their own.

## Small Radius Consequences

A 10-metre radius is deliberate but has real costs, and they should be
planned for:

-   **Adjacent rooms may fall inside the circle.** Ten metres from the
    centre of a classroom often reaches the room next door. The network
    and token layers are what separate them, not the radius.
-   **Large halls may fall outside it.** A lecture theatre can be 30 m
    long, so students at the back will sit beyond a 10 m radius centred
    on the front. For large venues either raise that location's radius to
    cover the room, or place the coordinates at the centre rather than at
    the podium. This is a per-location setting for exactly this reason.
-   **Coordinates must be right.** At this radius a centre entered from a
    map pin instead of measured in the room rejects the whole class. This
    is largely solved by anchoring on the teacher's own position — see
    [Where the circle is centred](#where-the-circle-is-centred) — but the
    saved coordinates still matter as the fallback for when the teacher's
    device cannot get a fix.

## Shared Devices

A student with no smartphone cannot mark attendance, and device binding
means they cannot borrow one. The teacher override is the intended path;
institutions should decide their policy on this before rollout.

------------------------------------------------------------------------

# Anti-Proxy Mechanisms - Status

Because "no chance of proxy" is a core requirement, most of what would
normally be optional hardening is part of the base system.

## In the core design

-   Teacher-generated rotating QR code.
-   Short-lived one-time session token.
-   Classroom network verification.
-   Device registration and binding.
-   One-device-one-student-per-session constraint.
-   Server-side session and window validation.
-   GPS accuracy validation.
-   Time-limited attendance windows (default 120 s).
-   Mock-location heuristics and flagging.
-   Full attempt logging and teacher-visible anomaly roster.

## Still optional / requires a mobile app

-   **BLE beacon proximity.** The strongest available proximity proof —
    Bluetooth Low Energy simply does not carry beyond about 10 m through
    walls, which matches the radius requirement physically rather than
    statistically. Browsers cannot scan for beacons, so this needs the
    native app.
-   **Wi-Fi BSSID matching.** Per-access-point verification instead of
    per-egress-IP. Also app-only.
-   **Play Integrity / DeviceCheck attestation.** Confirms the app is
    running unmodified on a genuine device, which closes the rooted-phone
    gap.
-   **Randomised second check-in.** A brief re-verification partway
    through the lecture, catching the student who marks in and leaves.

If the project later needs a stronger guarantee than the web version can
give, **BLE beacon + attestation in a native app** is the upgrade path
that adds the most, in that order.

------------------------------------------------------------------------

# Future Scope

The project can be extended with:

## Mobile Application

Build dedicated Android/iOS applications using:

-   Flutter
-   React Native
-   Native Android

## Push Notifications

Notify students when:

-   Attendance session starts.
-   Attendance is successfully marked.
-   Attendance is rejected.
-   Attendance percentage becomes low.

## QR + GPS Verification

Teacher displays a dynamic QR code while students must also be within
the GPS geofence.

``` text
Student
   |
   +---- Scan QR
   |
   +---- Verify GPS
   |
   +---- Verify Session
   |
   v
Attendance
```

## Analytics Dashboard

Display:

-   Attendance percentage.
-   Monthly trends.
-   Most frequently absent students.
-   Subject-wise attendance.
-   Class attendance trends.

## Cloud Deployment

The application can be deployed using:

-   AWS
-   Azure
-   Google Cloud
-   Render
-   Railway
-   Other cloud platforms

## Database Upgrade

Move from SQLite to:

``` text
MySQL
PostgreSQL
```

for larger deployments.

## Role-Based Access Control

Implement granular permissions for:

``` text
Super Admin
Department Admin
Teacher
Student
```

## Multi-Campus Support

A future version could support multiple campuses and buildings:

``` text
University
   |
   +---- Campus A
   |       |
   |       +---- Building 1
   |       +---- Building 2
   |
   +---- Campus B
           |
           +---- Building 1
```

------------------------------------------------------------------------

# Testing

Testing should cover both normal and abnormal conditions.

## Unit Testing

Test individual components such as:

-   Distance calculation.
-   Password validation.
-   Attendance validation.
-   Duplicate detection.
-   Report generation.

## Integration Testing

Test:

``` text
Frontend -> Flask API -> Database
```

and:

``` text
Student -> GPS -> Backend -> Attendance Database
```

## User Acceptance Testing

Test the application with:

-   Students.
-   Teachers.
-   Administrators.

------------------------------------------------------------------------

# Sample Test Cases

  Test Case   Input/Condition                             Expected Result
  ----------- ------------------------------------------- -------------------------------
  TC01        Valid student login                         Login successful
  TC02        Invalid password                            Login rejected
  TC03        Window open + all layers pass               Attendance marked
  TC04        Window open + 4 m away, accuracy 8 m        Attendance marked
  TC05        Window open + 28 m away, accuracy 24 m      Attendance marked (credit)
  TC06        Window open + 55 m away, accuracy 12 m      Rejected OUTSIDE_RADIUS
  TC07        Duplicate attendance                        Duplicate rejected
  TC08        GPS permission denied                       User asked to enable location
  TC09        Invalid coordinates                         Request rejected
  TC10        Student from another class                  Rejected NOT_ENROLLED
  TC11        Accuracy 90 m                               Retry prompt, not a rejection
  TC12        Valid attendance                            Record stored in database
  TC13        Generate monthly report                     Report generated
  TC14        Export attendance                           Excel/PDF generated

## Teacher-gate test cases

  Test Case   Input/Condition                             Expected Result
  ----------- ------------------------------------------- -------------------------------
  TG01        Session SCHEDULED, student marks            Rejected WINDOW_NOT_OPEN
  TG02        No session exists, crafted request          Rejected WINDOW_NOT_OPEN
  TG03        Teacher opens window, student marks         Attendance marked
  TG04        Teacher closes window, student marks        Rejected WINDOW_NOT_OPEN
  TG05        Window expired by timer, student marks      Rejected WINDOW_EXPIRED
  TG06        Session ACTIVE but closes_at in the past    Auto-closed and rejected
  TG07        Student requests token while closed         Rejected 403
  TG08        Non-owning teacher opens the window         Rejected 403
  TG09        Teacher reopens a CLOSED session            Rejected, CLOSED is terminal

## Anti-proxy test cases

  Test Case   Input/Condition                             Expected Result
  ----------- ------------------------------------------- -------------------------------
  AP01        Token from a previous rotation (20 s old)   Rejected TOKEN_EXPIRED
  AP02        Token from a different session              Rejected TOKEN_INVALID
  AP03        No token supplied                           Rejected TOKEN_MISSING
  AP04        Guessed/random token value                  Rejected TOKEN_INVALID
  AP05        Request from mobile data, off-campus        Rejected WRONG_NETWORK
  AP06        Spoofed X-Forwarded-For header              Rejected, header not trusted
  AP07        Correct GPS, wrong network                  Rejected WRONG_NETWORK
  AP08        Login on an unregistered second phone       Rejected DEVICE_NOT_REGISTERED
  AP09        One phone marks for two students            Second rejected DEVICE_ALREADY_USED
  AP10        Mock-location flag set (app)                Rejected INVALID_LOCATION
  AP11        Coordinates exactly equal to classroom      FLAGGED for teacher review
  AP12        Same account, impossible travel             FLAGGED for teacher review
  AP13        20 rapid attempts by one student            Rate limited
  AP14        Two simultaneous requests, same student     Exactly one record (unique key)
  AP15        Two simultaneous requests, same device      Exactly one record (unique key)
  AP16        Every rejection above                       Row written to attendance_attempts

TC05 and TC06 together are the pair worth running at the real classroom
before rollout — they are what prove the 10-metre radius admits the
people in the room and refuses the people outside it. If TC05 fails in
your building, raise `ACCURACY_CREDIT_METERS`; if TC06 passes when it
should not, lower it.

------------------------------------------------------------------------

# Example Database Record

After successful attendance:

``` text
Attendance ID      : 501
Student ID         : 101
Session ID         : 12

Date               : 17-08-2026
Time               : 11:25:14

Latitude           : 28.613935
Longitude          : 77.209021

Accuracy           : 8.4 metres
Distance           : 4.2 metres
Effective Distance : 0.0 metres
Allowed Radius     : 10 metres

Device ID          : 88
Token ID           : 1471
Source IP          : 203.0.113.44

Verification Flags : WINDOW_OK|TOKEN_OK|NETWORK_OK|
                     DEVICE_OK|GEOFENCE_OK

Status             : PRESENT
```

And a rejected attempt, stored in `attendance_attempts`:

``` text
Attempt ID     : 2210
Student ID     : 117
Session ID     : 12
Attempted At   : 17-08-2026 11:25:41

Result         : REJECTED
Failure Reason : WRONG_NETWORK

Latitude       : 28.613901
Longitude      : 77.209004
Accuracy       : 4.0 metres
Distance       : 0.4 metres

Device Hash    : d4f9a1...
Source IP      : 198.51.100.9
```

Note what this row shows: coordinates almost exactly on the classroom
point, with suspiciously good accuracy, arriving from an off-campus
address. Perfect GPS, failed anyway — which is the design working as
intended.

------------------------------------------------------------------------

# Example Report

A monthly report could look like:

``` text
=========================================================
             MONTHLY ATTENDANCE REPORT
=========================================================

Student : Gaurav Roy
Roll No : 101
Class   : CSE 3A

---------------------------------------------------------
Subject              Present    Total    Percentage
---------------------------------------------------------
Data Structures         22        25       88.00%
DBMS                    20        24       83.33%
Operating Systems       21        25       84.00%
Computer Networks       23        25       92.00%
---------------------------------------------------------

Overall Attendance: 86.10%
=========================================================
```

------------------------------------------------------------------------

# Suggested UI Pages

## Student

``` text
/login
/student/dashboard
/student/attendance
/student/history
/student/profile
```

## Teacher

``` text
/teacher/login
/teacher/dashboard
/teacher/sessions
/teacher/sessions/create
/teacher/sessions/<id>
/teacher/reports
```

## Admin

``` text
/admin/login
/admin/dashboard
/admin/students
/admin/teachers
/admin/departments
/admin/classes
/admin/subjects
/admin/locations
/admin/reports
```

------------------------------------------------------------------------

# Error Messages

The application should provide user-friendly messages.

### GPS Permission Denied

``` text
Location permission is required to mark attendance.
Please enable location access and try again.
```

### Outside Geofence

``` text
Attendance could not be marked.

You are approximately 183 metres away from
the classroom.

Allowed distance: 10 metres.
```

### Duplicate Attendance

``` text
Attendance has already been marked for this session.
```

### Window Not Open

``` text
Your teacher has not opened attendance yet.

The button will appear here as soon as the
attendance window starts.
```

### Window Closed or Expired

``` text
The attendance window has closed.

Please speak to your teacher if you were
present but could not mark in time.
```

### Token Expired

``` text
That QR code has already changed.

Point your camera at the screen again -
the code refreshes every 30 seconds.
```

### Wrong Network

``` text
You must be connected to the classroom
Wi-Fi network to mark attendance.

Connect to "CS-Block-204" and try again.
```

### Unregistered Device

``` text
This device is not registered to your account.

Attendance can only be marked from your
registered device. To change devices, request
approval from your teacher.
```

### Device Already Used

``` text
This device has already marked attendance for
another student in this session.
```

### Poor GPS Accuracy

``` text
Your current GPS accuracy is too low.
Please move away from the window or wait a
moment, then try again.
```

Error messages should say which layer failed and what the student can do
about it. A single generic "attendance failed" turns every honest
Wi-Fi problem into a complaint the teacher has to debug during class.

------------------------------------------------------------------------

# Project Report Structure

The academic project report can be organized into the following
chapters:

## Chapter 1 - Introduction

Explain:

-   Background.
-   Need for digital attendance.
-   GPS/geofencing concept.
-   Motivation for the project.

## Chapter 2 - Problem Statement

Explain the problems with manual attendance and proxy attendance.

## Chapter 3 - Objectives

Describe the goals of the system.

## Chapter 4 - Existing System

Discuss:

-   Manual attendance.
-   Paper registers.
-   Basic spreadsheet attendance.
-   Their limitations.

## Chapter 5 - Proposed System

Explain:

-   Student application.
-   Teacher panel.
-   Admin panel.
-   GPS verification.
-   Geofencing.
-   Attendance database.

## Chapter 6 - Hardware and Software Requirements

### Hardware

-   Smartphone/laptop.
-   Internet connection.
-   GPS-capable device.

### Software

-   Python.
-   Flask.
-   HTML/CSS/JavaScript.
-   SQLite/MySQL.
-   Web browser.
-   VS Code.

## Chapter 7 - System Design

Include:

-   System architecture.
-   Use-case diagram.
-   Data-flow diagram.
-   Activity diagram.
-   Sequence diagram.

## Chapter 8 - Database Design

Include:

-   ER diagram.
-   Tables.
-   Primary keys.
-   Foreign keys.
-   Relationships.

## Chapter 9 - Implementation

Explain:

-   Authentication.
-   GPS acquisition.
-   Haversine distance calculation.
-   Attendance validation.
-   Database operations.
-   Reports.

## Chapter 10 - Screenshots/Output

Include screenshots of:

-   Login.
-   Student dashboard.
-   Mark attendance.
-   GPS verification.
-   Successful attendance.
-   Rejected attendance.
-   Teacher dashboard.
-   Admin dashboard.
-   Attendance report.

## Chapter 11 - Advantages and Limitations

Explain the benefits and limitations of the system.

## Chapter 12 - Future Scope

Discuss:

-   Mobile application.
-   QR + GPS.
-   Analytics.
-   Cloud deployment.
-   Notifications.
-   Multi-campus support.

## Chapter 13 - Conclusion

Summarize how the system provides a digital, location-aware attendance
mechanism.

## Chapter 14 - References

Add the documentation and learning resources actually used during
implementation.

------------------------------------------------------------------------

# Recommended Diagrams for the Project

For a college mini-project, the following diagrams can make the
documentation stronger:

### 1. Use Case Diagram

Actors:

``` text
Student
Teacher
Admin
```

Use cases:

``` text
Student
  -> Login
  -> Mark Attendance
  -> View Attendance
  -> View History

Teacher
  -> Login
  -> Open Attendance Window
  -> Close Attendance Window
  -> Override Attendance
  -> View Attendance
  -> Generate Report

Admin
  -> Manage Users
  -> Manage Locations
  -> Configure Radius
  -> Generate Reports
```

### 2. ER Diagram

Show relationships between:

``` text
Student
Teacher
Department
Class
Subject
Location
AttendanceSession
Attendance
```

### 3. Activity Diagram

Show:

``` text
Login
  |
Active Session?
  |
Get GPS
  |
Validate Location
  |
Already Marked?
  |
Save Attendance
```

### 4. Sequence Diagram

A sequence diagram can show communication between:

``` text
Student
Browser
Flask Server
Database
GPS
```

------------------------------------------------------------------------

# Example End-to-End Scenario

Consider a classroom with the following configuration:

``` text
Location:
CS Block - Room 204

Latitude:
28.613900

Longitude:
77.209000

Attendance Radius:
10 metres

Allowed Network:
203.0.113.44

Window Length:
120 seconds
```

## 11:24:30 - The teacher opens the window

Mr. Sharma has been teaching for twenty minutes. He presses **Open
Attendance**.

``` text
Session 12  status: SCHEDULED -> ACTIVE
opened_at : 11:24:30
closes_at : 11:26:30
```

The projector begins displaying a QR code that changes every 30 seconds.

Before this moment, every attendance request for session 12 — from any
student, anywhere — returned `WINDOW_NOT_OPEN`.

## 11:25:02 - Gaurav marks attendance

Gaurav, sitting in the third row, opens the app and scans the code.

The browser obtains:

``` text
Latitude  : 28.613935
Longitude : 77.209021
Accuracy  : 8.4 metres
```

The client posts the token, coordinates, and accuracy. The device
identifier travels in the signed cookie.

The backend evaluates the chain:

``` text
Window open?          11:25:02 is within 11:24:30-11:26:30   PASS
Token valid?          issued 11:24:45, expires 11:25:20      PASS
Source IP?            203.0.113.44 matches classroom         PASS
Device bound?         device 88 -> student 101               PASS
Device unused?        no record for device 88 in session 12  PASS
Enrolled?             student 101 is in CSE 3A               PASS
Coordinates sane?     in range, no mock flag                 PASS
Accuracy OK?          8.4 <= 50                              PASS
Geofence?             see below                              PASS
Duplicate?            no existing record                     PASS
```

The geofence calculation:

``` text
distance  = 4.2 m                    (Haversine)
credit    = min(8.4, 35) = 8.4 m
effective = 4.2 - 8.4 = -4.2 m
-4.2 <= 10                           INSIDE
```

The record is created:

``` text
Student ID  : 101
Session ID  : 12
Date        : 17-08-2026
Time        : 11:25:02
Latitude    : 28.613935
Longitude   : 77.209021
Distance    : 4.2 m
Device ID   : 88
Token ID    : 1471
Status      : PRESENT
```

Gaurav sees:

``` text
✓ Attendance marked successfully.
```

## 11:25:41 - Rohit tries from home

Rohit is absent. A classmate has sent them a photo of the QR code.

By the time they open the message and scan it, that token has expired at
11:25:20. They get `TOKEN_EXPIRED`.

They ask for a fresh photo and try again at 11:25:58 with a token that is
only 6 seconds old — and a mock-location app reporting the classroom
coordinates exactly.

``` text
Window open?     PASS
Token valid?     PASS   (fresh photo, within TTL)
Source IP?       198.51.100.9 is not 203.0.113.44
                 REJECT  WRONG_NETWORK
```

The chain stops there. His perfect coordinates are never even evaluated.
A row is written to `attendance_attempts`, and Mr. Sharma's roster shows:

``` text
⚠ Rohit Verma - REJECTED (WRONG_NETWORK) at 11:25:58
```

## 11:26:04 - Priya lends a phone

Priya has already marked in. Their friend Anjali left a phone at home, so
Priya logs Anjali in on Priya's device.

``` text
Window open?     PASS
Token valid?     PASS
Source IP?       PASS   (both are in the room)
Device bound?    device 91 belongs to Priya, not Anjali
                 REJECT  DEVICE_NOT_REGISTERED
```

Anjali is genuinely present, so the correct resolution is the teacher
override — which Mr. Sharma applies, and which is logged as a manual
action with that teacher's id against it.

## 11:26:30 - The window closes

The session auto-closes. All outstanding tokens are invalidated. Session
12 is now `CLOSED` and terminal — no further attendance can be recorded
for it by anyone, including the teacher, except through the audited
override path.

``` text
Marked   : 58 / 62
Rejected : 3
Flagged  : 0
Override : 1
```

------------------------------------------------------------------------

# Important Implementation Principle

The most important security rule in this project is:

> **The frontend decides nothing. It gathers signals; the backend
> decides.**

The frontend obtains the coordinates and the scanned token and sends
them. Every judgement is made server-side.

The backend independently:

1.  Authenticates the student.
2.  **Confirms the teacher has the window open, by timestamp.**
3.  Validates the token against server-side storage.
4.  Reads the source IP from the connection and checks it.
5.  Reads the device identity from the signed cookie and checks it.
6.  Confirms the device has not already marked for someone else.
7.  Verifies class/session eligibility.
8.  Validates latitude, longitude, and mock-location signals.
9.  Checks GPS accuracy.
10. Retrieves the authorized location and calculates the distance.
11. Applies the accuracy-aware 10 m geofence test.
12. Checks duplicate attendance.
13. Saves the attendance record.
14. Logs the attempt, whatever the outcome.

This prevents a client-side check from being the only protection.

The corollary matters just as much: **a single check is not a security
design.** Any one of these layers can be defeated by a sufficiently
motivated student. What makes proxy impractical is that they must all be
defeated at the same time, within a two-minute window, without knowing in
advance when that window will open.

------------------------------------------------------------------------

# Conclusion

The **GPS Self-Attendance System** provides a practical solution for
digitizing college attendance.

Instead of relying entirely on manual attendance, the system allows
students to check in through a web/mobile interface while the backend
verifies that they are physically in the classroom.

The combination of:

``` text
Student Authentication
        +
Teacher-Opened Attendance Window   <-- the gate
        +
Rotating One-Time QR Token
        +
Classroom Network Verification
        +
Device Binding
        +
GPS Location + 10 m Geofencing
        +
Server-Side Validation
        +
Attendance Database + Attempt Log
        +
Reports
```

creates a complete attendance management workflow.

## How the three requirements are met

**A 10-metre radius** is the configured geofence, enforced with an
accuracy-aware comparison so that GPS noise does not falsely reject
students who are genuinely in the room. A naive 10 m check against a raw
reading was rejected as a design because it would be unreliable in
practice.

**Attendance only when the teacher turns it on** is a server-side state
machine, not a UI affordance. With no `ACTIVE` window, every request from
every student is refused; the window auto-expires; `CLOSED` is terminal.

**No chance of proxy** is approached honestly. No self-service system can
make proxy impossible, because the student holds the sensor. What this
design achieves is that casual proxy — the screenshot to an absent
friend, the borrowed phone, the spoofed GPS — fails at one layer or
another, and every attempt is logged for the teacher to see. Defeating
all layers at once requires a physically present accomplice, at which
point proxy has become harder than attending.

## As a project

The project is suitable as a college mini-project because it
demonstrates several important software engineering concepts, including:

-   Frontend development.
-   Backend API development.
-   Database design and constraint-based integrity.
-   Authentication and device binding.
-   REST APIs.
-   GPS/geolocation and measurement error handling.
-   Geofencing.
-   Layered security design and threat modelling.
-   Server-side validation.
-   Audit logging.
-   Report generation.
-   Role-based access control.

It can also serve as a foundation for a larger production system by
adding BLE proximity, device attestation, mobile applications, cloud
deployment, analytics, and notifications.
