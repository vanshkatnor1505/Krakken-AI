
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import Kraken

Item {
    id: root

    // ==========================================================
    // PUBLIC API
    // ==========================================================

    property string state: "idle"

    property bool showHeader: true
    property bool showTimestamps: true
    property bool autoScroll: true

    property int maxMessages: 200

    // Focus mode.
    // This is intentionally NOT desktop fullscreen.
    property bool fullscreen: false

    // Backend bridge.
    property var assistantBridge: null

    // AI-generated highlights.
    property bool showHighlights: true
    property string currentHighlights: ""

    // Controls whether the current highlight card is visible.
    property bool highlightsVisible:
        root.showHighlights &&
        root.currentHighlights.length > 0

    signal messageSent(string message)
    signal clearRequested()
    signal streamingStarted()
    signal streamingFinished()

    // ==========================================================
    // SIZE
    // ==========================================================

    implicitWidth: 700
    implicitHeight: 520

    // ==========================================================
    // STATE COLOR
    // ==========================================================

    property color stateColor: {

        switch (root.state) {

        case "listening":
            return Theme.accentGreen

        case "thinking":
            return Theme.accentPurple

        case "processing":
            return Theme.warning

        case "speaking":
            return Theme.accent

        case "error":
            return Theme.danger

        default:
            return Theme.accent
        }
    }

    // ==========================================================
    // STREAMING
    // ==========================================================

    property bool streaming: false
    property int streamingIndex: -1

    // ==========================================================
    // MESSAGE MODEL
    // ==========================================================

    ListModel {
        id: messageModel
    }

    // ==========================================================
    // ASSISTANT BRIDGE CONNECTION
    // ==========================================================

    Connections {

        id: assistantConnections

        target: root.assistantBridge

        // ------------------------------------------------------
        // BACKEND STATE
        // ------------------------------------------------------

        function onStateChanged(state) {

            if (!state)
                return

            root.state = state
        }

        // ------------------------------------------------------
        // RESPONSE STARTED
        // ------------------------------------------------------

        function onResponseStarted() {

            root.startStreaming()
        }

        // ------------------------------------------------------
        // RESPONSE CHUNK
        // ------------------------------------------------------

        function onResponseChunk(chunk) {

            if (!chunk)
                return

            root.appendStreamText(
                chunk
            )
        }

        // ------------------------------------------------------
        // RESPONSE FINISHED
        // ------------------------------------------------------

        function onResponseFinished() {

            root.finishStreaming()
        }

        // ------------------------------------------------------
        // BACKEND ERROR
        // ------------------------------------------------------

        function onErrorOccurred(error) {

            root.cancelStreaming()

            root.state = "error"

            if (
                error &&
                error.length > 0
            ) {

                root.addAssistantMessage(
                    "Error: " + error
                )
            }
        }

        // ------------------------------------------------------
        // AI HIGHLIGHTS
        //
        // THIS WAS THE MISSING CONNECTION.
        //
        // AssistantBridge:
        //
        //     highlightsReady(str)
        //
        // becomes:
        //
        //     ChatView.showAIHighlights(str)
        // ------------------------------------------------------

        function onHighlightsReady(highlights) {

            if (!highlights)
                return

            root.showAIHighlights(
                highlights
            )
        }
    }

    // ==========================================================
    // FOCUS MODE WINDOW
    // ==========================================================

    Window {

        id: focusWindow

        visible: false

        width: 1100
        height: 720

        minimumWidth: 800
        minimumHeight: 500

        title: "KRAKKEN — Focus Mode"

        flags:
            Qt.Window |
            Qt.WindowTitleHint |
            Qt.WindowSystemMenuHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint

        color:
            Qt.rgba(
                0.025,
                0.04,
                0.07,
                1.0
            )

        modality: Qt.NonModal

        onClosing: function(close) {

            close.accepted = true

            root.exitFullscreen()
        }

        Rectangle {

            anchors.fill: parent

            color:
                Qt.rgba(
                    0.025,
                    0.04,
                    0.07,
                    1.0
                )
        }
    }

    // ==========================================================
    // MAIN CHAT PANEL
    // ==========================================================

    Rectangle {

        id: panel

        anchors.fill: parent

        radius:
            root.fullscreen
            ? 16
            : Theme.radiusLarge

        color:
            Qt.rgba(
                0.04,
                0.07,
                0.12,
                0.94
            )

        border.width: 1

        border.color:
            Qt.rgba(
                1,
                1,
                1,
                0.055
            )

        // ======================================================
        // HEADER
        // ======================================================

        Rectangle {

            id: header

            visible:
                root.showHeader

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right

            height:
                root.fullscreen
                ? 68
                : 58

            color: "transparent"

            RowLayout {

                anchors.fill: parent

                anchors.leftMargin:
                    root.fullscreen
                    ? 28
                    : 24

                anchors.rightMargin:
                    root.fullscreen
                    ? 22
                    : 18

                spacing: 12

                Rectangle {

                    Layout.alignment:
                        Qt.AlignVCenter

                    width: 7
                    height: 7

                    radius: 3.5

                    color:
                        root.stateColor

                    SequentialAnimation on opacity {

                        running:
                            root.state !== "idle"

                        loops:
                            Animation.Infinite

                        NumberAnimation {
                            from: 0.35
                            to: 1
                            duration: 650
                        }

                        NumberAnimation {
                            from: 1
                            to: 0.35
                            duration: 650
                        }
                    }
                }

                ColumnLayout {

                    Layout.fillWidth: true

                    spacing: 2

                    Text {

                        text: "KRAKKEN"

                        color:
                            Theme.textPrimary

                        font.pixelSize:
                            root.fullscreen
                            ? 15
                            : 13

                        font.bold: true

                        font.letterSpacing: 2.2
                    }

                    Text {

                        text:
                            root.fullscreen
                            ? "FOCUS MODE • "
                              + stateDescription()
                            : stateDescription()

                        color:
                            root.stateColor

                        font.pixelSize: 8

                        font.bold: true

                        font.letterSpacing: 1.6

                        opacity: 0.72
                    }
                }

                Text {

                    Layout.alignment:
                        Qt.AlignVCenter

                    text:
                        messageModel.count
                        + " MESSAGES"

                    color:
                        Theme.textSecondary

                    font.pixelSize: 8

                    font.letterSpacing: 1

                    opacity: 0.55
                }

                Rectangle {

                    Layout.alignment:
                        Qt.AlignVCenter

                    width: 34
                    height: 34

                    radius: 9

                    color:
                        fullscreenMouse.containsMouse
                        ? Qt.rgba(
                            1,
                            1,
                            1,
                            0.07
                        )
                        : "transparent"

                    Text {

                        anchors.centerIn: parent

                        text:
                            root.fullscreen
                            ? "⤢"
                            : "⛶"

                        color:
                            Theme.textSecondary

                        font.pixelSize: 17

                        opacity: 0.75
                    }

                    MouseArea {

                        id: fullscreenMouse

                        anchors.fill: parent

                        hoverEnabled: true

                        cursorShape:
                            Qt.PointingHandCursor

                        onClicked:
                            root.toggleFullscreen()
                    }

                    ToolTip.visible:
                        fullscreenMouse.containsMouse

                    ToolTip.text:
                        root.fullscreen
                        ? "Return to normal chat"
                        : "Open Focus Mode"
                }

                Rectangle {

                    Layout.alignment:
                        Qt.AlignVCenter

                    width: 30
                    height: 30

                    radius: 9

                    color:
                        clearMouse.containsMouse
                        ? Qt.rgba(
                            1,
                            1,
                            1,
                            0.06
                        )
                        : "transparent"

                    Text {

                        anchors.centerIn: parent

                        text: "×"

                        color:
                            Theme.textSecondary

                        font.pixelSize: 18

                        opacity: 0.65
                    }

                    MouseArea {

                        id: clearMouse

                        anchors.fill: parent

                        hoverEnabled: true

                        cursorShape:
                            Qt.PointingHandCursor

                        onClicked: {

                            root.clearMessages()

                            root.clearRequested()
                        }
                    }

                    ToolTip.visible:
                        clearMouse.containsMouse

                    ToolTip.text:
                        "Clear conversation"
                }
            }

            Rectangle {

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom

                height: 1

                color:
                    Qt.rgba(
                        1,
                        1,
                        1,
                        0.035
                    )
            }
        }

        // ======================================================
        // MESSAGE LIST
        // ======================================================

        ListView {

            id: messageList

            anchors.left: parent.left
            anchors.right: parent.right

            anchors.top:
                root.showHeader
                ? header.bottom
                : parent.top

            anchors.bottom: parent.bottom

            anchors.leftMargin:
                root.fullscreen
                ? 42
                : 22

            anchors.rightMargin:
                root.fullscreen
                ? 42
                : 18

            anchors.topMargin:
                root.fullscreen
                ? 22
                : 14

            anchors.bottomMargin:
                root.highlightsVisible
                ? (
                    highlightsCard.height +
                    (
                        root.fullscreen
                        ? 36
                        : 28
                    )
                )
                : (
                    root.fullscreen
                    ? 28
                    : 16
                )

            clip: true

            model: messageModel

            spacing:
                root.fullscreen
                ? 22
                : 18

            boundsBehavior:
                Flickable.StopAtBounds

            ScrollBar.vertical:
                ScrollBar {
                    policy:
                        ScrollBar.AsNeeded
                }

            // ==================================================
            // EMPTY STATE
            // ==================================================

            Text {

                anchors.centerIn: parent

                visible:
                    messageModel.count === 0

                text:
                    "AWAITING COMMAND"

                color:
                    Theme.textSecondary

                opacity: 0.28

                font.pixelSize: 10

                font.bold: true

                font.letterSpacing: 3
            }

            // ==================================================
            // MESSAGE DELEGATE
            // ==================================================

            delegate: Item {

                id: messageDelegate

                width:
                    messageList.width

                height:
                    messageContent.height + 12

                property bool isUser:
                    role === "user"

                property real maximumBubbleWidth:
                    messageList.width *
                    (
                        root.fullscreen
                        ? 0.78
                        : 0.82
                    )

                opacity: 0

                transform:
                    Translate {

                        x:
                            messageDelegate.isUser
                            ? 16
                            : -16
                    }

                Component.onCompleted: {

                    messageDelegate.opacity = 1

                    messageDelegate.x = 0
                }

                Behavior on opacity {

                    NumberAnimation {

                        duration: 280

                        easing.type:
                            Easing.OutCubic
                    }
                }

                Behavior on x {

                    NumberAnimation {

                        duration: 280

                        easing.type:
                            Easing.OutCubic
                    }
                }

                Column {

                    id: messageContent

                    width:
                        Math.min(
                            messageDelegate.maximumBubbleWidth,
                            Math.max(
                                160,
                                messageText.implicitWidth + 30
                            )
                        )

                    anchors.right:
                        messageDelegate.isUser
                        ? parent.right
                        : undefined

                    anchors.left:
                        messageDelegate.isUser
                        ? undefined
                        : parent.left

                    spacing: 6

                    Row {

                        spacing: 8

                        anchors.right:
                            messageDelegate.isUser
                            ? parent.right
                            : undefined

                        Text {

                            text:
                                messageDelegate.isUser
                                ? "YOU"
                                : "KRAKKEN"

                            color:
                                messageDelegate.isUser
                                ? Theme.textSecondary
                                : root.stateColor

                            font.pixelSize: 8

                            font.bold: true

                            font.letterSpacing: 2

                            opacity:
                                messageDelegate.isUser
                                ? 0.65
                                : 0.9
                        }

                        Text {

                            visible:
                                root.showTimestamps

                            text:
                                timestamp

                            color:
                                Theme.textSecondary

                            font.pixelSize: 8

                            opacity: 0.3
                        }
                    }

                    Rectangle {

                        id: messageBubble

                        width:
                            Math.min(
                                messageDelegate.maximumBubbleWidth,
                                Math.max(
                                    160,
                                    messageText.implicitWidth + 30
                                )
                            )

                        height:
                            Math.max(
                                root.fullscreen
                                ? 52
                                : 48,
                                messageText.implicitHeight + 22
                            )

                        anchors.right:
                            messageDelegate.isUser
                            ? parent.right
                            : undefined

                        radius:
                            root.fullscreen
                            ? 15
                            : 13

                        color:
                            messageDelegate.isUser
                            ? Qt.rgba(
                                0.10,
                                0.14,
                                0.21,
                                0.72
                            )
                            : Qt.rgba(
                                0.05,
                                0.08,
                                0.14,
                                0.82
                            )

                        border.width: 1

                        border.color:
                            messageDelegate.isUser
                            ? Qt.rgba(
                                1,
                                1,
                                1,
                                0.055
                            )
                            : Qt.rgba(
                                root.stateColor.r,
                                root.stateColor.g,
                                root.stateColor.b,
                                0.16
                            )

                        Rectangle {

                            visible:
                                !messageDelegate.isUser

                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom

                            width: 2

                            radius: 1

                            color:
                                root.stateColor

                            opacity: 0.7
                        }

                        Text {

                            id: messageText

                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom

                            anchors.leftMargin:
                                root.fullscreen
                                ? 17
                                : 15

                            anchors.rightMargin:
                                root.fullscreen
                                ? 17
                                : 15

                            anchors.topMargin: 11
                            anchors.bottomMargin: 11

                            text:
                                message

                            color:
                                Theme.textPrimary

                            font.pixelSize:
                                root.fullscreen
                                ? 14
                                : 13

                            lineHeight: 1.4

                            wrapMode:
                                Text.Wrap

                            textFormat:
                                Text.PlainText

                            horizontalAlignment:
                                messageDelegate.isUser
                                ? Text.AlignRight
                                : Text.AlignLeft

                            verticalAlignment:
                                Text.AlignVCenter
                        }
                    }
                }
            }

            // ==================================================
            // THINKING INDICATOR
            // ==================================================

            footer: Item {

                width:
                    messageList.width

                height:
                    root.state === "thinking" ||
                    root.state === "processing"
                    ? 44
                    : 0

                visible:
                    root.state === "thinking" ||
                    root.state === "processing"

                Row {

                    anchors.left:
                        parent.left

                    anchors.leftMargin: 4

                    anchors.verticalCenter:
                        parent.verticalCenter

                    spacing: 8

                    Text {

                        text:
                            root.state === "processing"
                            ? "PROCESSING"
                            : "THINKING"

                        color:
                            root.stateColor

                        font.pixelSize: 8

                        font.bold: true

                        font.letterSpacing: 2

                        opacity: 0.75
                    }

                    Row {

                        spacing: 4

                        anchors.verticalCenter:
                            parent.verticalCenter

                        Repeater {

                            model: 3

                            delegate:
                                Rectangle {

                                    width: 4
                                    height: 4

                                    radius: 2

                                    color:
                                        root.stateColor

                                    opacity: 0.25

                                    SequentialAnimation on opacity {

                                        running: true

                                        loops:
                                            Animation.Infinite

                                        PauseAnimation {
                                            duration:
                                                index * 160
                                        }

                                        NumberAnimation {
                                            from: 0.25
                                            to: 1
                                            duration: 320
                                        }

                                        NumberAnimation {
                                            from: 1
                                            to: 0.25
                                            duration: 320
                                        }
                                    }
                                }
                        }
                    }
                }
            }

            onCountChanged:
                root.scrollToBottom()
        }

        // ======================================================
        // KEY HIGHLIGHTS
        //
        // Temporary AI briefing displayed before the response.
        // ======================================================

        Rectangle {

            id: highlightsCard

            visible:
                root.highlightsVisible

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom

            anchors.leftMargin:
                root.fullscreen
                ? 42
                : 22

            anchors.rightMargin:
                root.fullscreen
                ? 42
                : 18

            anchors.bottomMargin:
                root.fullscreen
                ? 24
                : 16

            height:
                highlightsColumn.implicitHeight +
                28

            radius:
                root.fullscreen
                ? 17
                : 15

            color:
                Qt.rgba(
                    0.065,
                    0.09,
                    0.15,
                    0.985
                )

            border.width: 1

            border.color:
                Qt.rgba(
                    root.stateColor.r,
                    root.stateColor.g,
                    root.stateColor.b,
                    0.26
                )

            z: 20

            opacity:
                root.highlightsVisible
                ? 1
                : 0

            transform:
                Translate {

                    y:
                        root.highlightsVisible
                        ? 0
                        : 12
                }

            Behavior on opacity {

                NumberAnimation {

                    duration: 220

                    easing.type:
                        Easing.OutCubic
                }
            }

            Behavior on y {

                NumberAnimation {

                    duration: 220

                    easing.type:
                        Easing.OutCubic
                }
            }

            // --------------------------------------------------
            // LEFT ACCENT
            // --------------------------------------------------

            Rectangle {

                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom

                width: 3

                radius: 1.5

                color:
                    root.stateColor

                opacity: 0.8
            }

            // --------------------------------------------------
            // TOP GLOW
            // --------------------------------------------------

            Rectangle {

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top

                height: 1

                color:
                    Qt.rgba(
                        root.stateColor.r,
                        root.stateColor.g,
                        root.stateColor.b,
                        0.35
                    )
            }

            Column {

                id: highlightsColumn

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top

                anchors.leftMargin:
                    root.fullscreen
                    ? 20
                    : 18

                anchors.rightMargin:
                    root.fullscreen
                    ? 20
                    : 18

                anchors.topMargin: 14

                spacing: 8

                // --------------------------------------------------
                // HEADER
                // --------------------------------------------------

                RowLayout {

                    width: parent.width

                    spacing: 8

                    Text {

                        text: "✦"

                        color:
                            root.stateColor

                        font.pixelSize:
                            root.fullscreen
                            ? 14
                            : 13

                        Layout.alignment:
                            Qt.AlignVCenter
                    }

                    Text {

                        text:
                            "KEY HIGHLIGHTS"

                        color:
                            Theme.textPrimary

                        font.pixelSize:
                            root.fullscreen
                            ? 9
                            : 8

                        font.bold: true

                        font.letterSpacing: 2.2

                        Layout.fillWidth: true

                        Layout.alignment:
                            Qt.AlignVCenter
                    }

                    Rectangle {

                        width: 6
                        height: 6

                        radius: 3

                        color:
                            root.stateColor

                        opacity: 0.8

                        Layout.alignment:
                            Qt.AlignVCenter
                    }
                }

                // --------------------------------------------------
                // HIGHLIGHT CONTENT
                // --------------------------------------------------

                Text {

                    width:
                        parent.width

                    text:
                        root.currentHighlights

                    color:
                        Theme.textPrimary

                    font.pixelSize:
                        root.fullscreen
                        ? 13
                        : 12

                    lineHeight:
                        1.35

                    wrapMode:
                        Text.Wrap

                    textFormat:
                        Text.PlainText

                    maximumLineCount: 4

                    elide:
                        Text.ElideRight
                }

                // --------------------------------------------------
                // FOOTER
                // --------------------------------------------------

                RowLayout {

                    width: parent.width

                    spacing: 6

                    Text {

                        text:
                            "AI BRIEFING"

                        color:
                            root.stateColor

                        font.pixelSize: 7

                        font.bold: true

                        font.letterSpacing: 1.5

                        opacity: 0.7
                    }

                    Item {
                        Layout.fillWidth: true
                    }

                    Text {

                        text:
                            "FULL RESPONSE ↓"

                        color:
                            Theme.textSecondary

                        font.pixelSize: 7

                        font.bold: true

                        font.letterSpacing: 1

                        opacity: 0.45
                    }
                }
            }
        }
    }

    // ==========================================================
    // PUBLIC MESSAGE API
    // ==========================================================

    function addUserMessage(text) {

        if (
            !text ||
            text.trim().length === 0
        )
            return

        messageModel.append({

            role: "user",

            message: text.trim(),

            timestamp: currentTime(),

            streaming: false
        })

        trimMessages()

        root.messageSent(
            text.trim()
        )

        scrollToBottom()
    }

    function addAssistantMessage(text) {

        if (
            !text ||
            text.trim().length === 0
        )
            return

        messageModel.append({

            role: "assistant",

            message: text,

            timestamp: currentTime(),

            streaming: false
        })

        trimMessages()

        scrollToBottom()
    }

    function addMessage(role, text) {

        if (
            !text ||
            text.trim().length === 0
        )
            return

        messageModel.append({

            role: role,

            message: text,

            timestamp: currentTime(),

            streaming: false
        })

        trimMessages()

        scrollToBottom()
    }

    // ==========================================================
    // HIGHLIGHT API
    // ==========================================================

    function showAIHighlights(text) {

        if (
            !text ||
            text.trim().length === 0
        )
            return

        root.currentHighlights =
            text.trim()

        // Keep the latest highlight visible.
        // The response itself will begin immediately afterward.
        root.scrollToBottom()
    }

    function clearHighlights() {

        root.currentHighlights = ""
    }

    // ==========================================================
    // STREAMING API
    // ==========================================================

    function startStreaming() {

        if (root.streaming)
            return

        // Highlights have served their purpose once
        // the actual response begins.
        root.clearHighlights()

        messageModel.append({

            role: "assistant",

            message: "",

            timestamp: currentTime(),

            streaming: true
        })

        root.streamingIndex =
            messageModel.count - 1

        root.streaming = true

        root.state = "speaking"

        root.streamingStarted()

        scrollToBottom()
    }

    function appendStreamText(text) {

        if (!root.streaming)
            return

        if (
            root.streamingIndex < 0 ||
            root.streamingIndex >= messageModel.count
        )
            return

        if (
            !text ||
            text.length === 0
        )
            return

        var currentMessage =
            messageModel.get(
                root.streamingIndex
            ).message

        messageModel.setProperty(
            root.streamingIndex,
            "message",
            currentMessage + text
        )

        scrollToBottom()
    }

    function finishStreaming() {

        if (!root.streaming)
            return

        if (
            root.streamingIndex >= 0 &&
            root.streamingIndex < messageModel.count
        ) {

            messageModel.setProperty(
                root.streamingIndex,
                "streaming",
                false
            )
        }

        root.streaming = false

        root.streamingIndex = -1

        root.streamingFinished()

        scrollToBottom()
    }

    function cancelStreaming() {

        if (!root.streaming)
            return

        root.streaming = false

        root.streamingIndex = -1
    }

    // ==========================================================
    // FOCUS MODE
    // ==========================================================

    function enterFullscreen() {

        if (root.fullscreen)
            return

        root.fullscreen = true

        var mainWindow =
            Window.window

        if (mainWindow) {

            focusWindow.width =
                Math.min(
                    1100,
                    Math.max(
                        800,
                        mainWindow.width - 140
                    )
                )

            focusWindow.height =
                Math.min(
                    720,
                    Math.max(
                        500,
                        mainWindow.height - 120
                    )
                )

            focusWindow.x =
                mainWindow.x +
                Math.round(
                    (
                        mainWindow.width -
                        focusWindow.width
                    ) / 2
                )

            focusWindow.y =
                mainWindow.y +
                Math.round(
                    (
                        mainWindow.height -
                        focusWindow.height
                    ) / 2
                )
        }

        panel.parent =
            focusWindow.contentItem

        panel.anchors.fill =
            focusWindow.contentItem

        panel.anchors.margins = 0

        focusWindow.show()

        focusWindow.raise()

        focusWindow.requestActivate()

        scrollToBottom()
    }

    function exitFullscreen() {

        if (!root.fullscreen)
            return

        panel.parent = root

        panel.anchors.fill = root

        panel.anchors.margins = 0

        root.fullscreen = false

        focusWindow.hide()

        scrollToBottom()
    }

    function toggleFullscreen() {

        if (root.fullscreen)
            root.exitFullscreen()
        else
            root.enterFullscreen()
    }

    // ==========================================================
    // UTILITIES
    // ==========================================================

    function scrollToBottom() {

        if (!root.autoScroll)
            return

        Qt.callLater(
            function() {

                if (
                    messageModel.count > 0
                ) {

                    messageList.positionViewAtEnd()
                }
            }
        )
    }

    function clearMessages() {

        messageModel.clear()

        root.streaming = false

        root.streamingIndex = -1

        root.clearHighlights()
    }

    function trimMessages() {

        while (
            messageModel.count >
            root.maxMessages
        ) {

            messageModel.remove(0)
        }
    }

    function currentTime() {

        var date =
            new Date()

        return Qt.formatTime(
            date,
            "hh:mm:ss"
        )
    }

    function stateDescription() {

        switch (root.state) {

        case "listening":
            return "LISTENING FOR INPUT"

        case "thinking":
            return "ANALYZING REQUEST"

        case "processing":
            return "PROCESSING TASK"

        case "speaking":
            return "GENERATING RESPONSE"

        case "error":
            return "SYSTEM ERROR"

        default:
            return "SYSTEM READY"
        }
    }

    // ==========================================================
    // ESCAPE KEY
    // ==========================================================

    Keys.onEscapePressed: {

        if (root.fullscreen) {

            root.exitFullscreen()
        }
    }

    // ==========================================================
    // INITIAL MESSAGE
    // ==========================================================

    Component.onCompleted: {

        addAssistantMessage(
            "Krakken AI initialized. Awaiting your command."
        )
    }
}

