
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

    property bool fullscreen: false

    // Assigned by the parent ApplicationWindow:
    //
    // ChatView {
    //     assistantBridge: assistantBridge
    // }
    //
    property var assistantBridge: null

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
        // STATE
        // ------------------------------------------------------

        function onStateChanged(state) {

            if (
                state === undefined ||
                state === null ||
                String(state).length === 0
            )
                return

            root.state = String(state)
        }

        // ------------------------------------------------------
        // RESPONSE STARTED
        // ------------------------------------------------------

        function onResponseStarted() {

            console.log(
                "QML CHATVIEW: RESPONSE STARTED"
            )

            root.startStreaming()
        }

        // ------------------------------------------------------
        // RESPONSE CHUNK
        // ------------------------------------------------------

        function onResponseChunk(chunk) {

            if (
                chunk === undefined ||
                chunk === null
            )
                return

            var text = String(chunk)

            if (text.length === 0)
                return

            root.appendStreamText(text)
        }

        // ------------------------------------------------------
        // RESPONSE FINISHED
        // ------------------------------------------------------

        function onResponseFinished() {

            console.log(
                "QML CHATVIEW: RESPONSE FINISHED"
            )

            root.finishStreaming()
        }

        // ------------------------------------------------------
        // ERROR
        // ------------------------------------------------------

        function onErrorOccurred(error) {

            root.cancelStreaming()

            root.state = "error"

            if (
                error !== undefined &&
                error !== null
            ) {

                var errorText =
                    String(error).trim()

                if (errorText.length > 0) {

                    root.addAssistantMessage(
                        "Error: " + errorText
                    )
                }
            }
        }
    }

    // ==========================================================
    // DEBUG BRIDGE STATUS
    // ==========================================================

    onAssistantBridgeChanged: {

        console.log(
            "CHATVIEW ASSISTANT BRIDGE:",
            root.assistantBridge
        )
    }

    // ==========================================================
    // FOCUS WINDOW
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

        modality:
            Qt.NonModal

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
    // MAIN PANEL
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
        // MAIN COLUMN
        // ======================================================

        ColumnLayout {

            anchors.fill: parent

            spacing: 0

            // ==================================================
            // HEADER
            // ==================================================

            Rectangle {

                id: header

                visible:
                    root.showHeader

                Layout.fillWidth: true

                Layout.preferredHeight:
                    root.showHeader
                    ? (
                        root.fullscreen
                        ? 68
                        : 58
                    )
                    : 0

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

                    // ------------------------------------------
                    // STATE INDICATOR
                    // ------------------------------------------

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

                    // ------------------------------------------
                    // TITLE
                    // ------------------------------------------

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
                                  + root.stateDescription()
                                : root.stateDescription()

                            color:
                                root.stateColor

                            font.pixelSize: 8

                            font.bold: true

                            font.letterSpacing: 1.6

                            opacity: 0.72
                        }
                    }

                    // ------------------------------------------
                    // MESSAGE COUNT
                    // ------------------------------------------

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

                    // ------------------------------------------
                    // FOCUS BUTTON
                    // ------------------------------------------

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

                    // ------------------------------------------
                    // CLEAR BUTTON
                    // ------------------------------------------

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

                // ----------------------------------------------
                // HEADER DIVIDER
                // ----------------------------------------------

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

            // ==================================================
            // MESSAGE LIST
            // ==================================================

            ListView {

                id: messageList

                Layout.fillWidth: true
                Layout.fillHeight: true

                Layout.leftMargin:
                    root.fullscreen
                    ? 42
                    : 22

                Layout.rightMargin:
                    root.fullscreen
                    ? 42
                    : 18

                Layout.topMargin:
                    root.fullscreen
                    ? 18
                    : 14

                Layout.bottomMargin:
                    root.fullscreen
                    ? 28
                    : 16

                clip: true

                model:
                    messageModel

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

                        // ------------------------------------------
                        // META
                        // ------------------------------------------

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

                        // ------------------------------------------
                        // MESSAGE BUBBLE
                        // ------------------------------------------

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

                            // --------------------------------------
                            // ASSISTANT ACCENT
                            // --------------------------------------

                            Rectangle {

                                visible:
                                    !messageDelegate.isUser

                                anchors.left:
                                    parent.left

                                anchors.top:
                                    parent.top

                                anchors.bottom:
                                    parent.bottom

                                width: 2

                                radius: 1

                                color:
                                    root.stateColor

                                opacity: 0.7
                            }

                            // --------------------------------------
                            // MESSAGE TEXT
                            // --------------------------------------

                            Text {

                                id: messageText

                                anchors.left:
                                    parent.left

                                anchors.right:
                                    parent.right

                                anchors.top:
                                    parent.top

                                anchors.bottom:
                                    parent.bottom

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

                                lineHeight:
                                    1.4

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

        var messageText =
            text.trim()

        messageModel.append({

            role: "user",

            message: messageText,

            timestamp: currentTime(),

            streaming: false
        })

        trimMessages()

        root.messageSent(
            messageText
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
    // STREAMING
    // ==========================================================

    function startStreaming() {

        if (root.streaming)
            return

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
    // ESCAPE
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

        console.log(
            "CHATVIEW INITIALIZED"
        )

        console.log(
            "CHATVIEW BRIDGE:",
            root.assistantBridge
        )

        addAssistantMessage(
            "Krakken AI initialized. Awaiting your command."
        )
    }
}

