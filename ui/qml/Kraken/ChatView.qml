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


    // ==========================================================
    // PYTHON ASSISTANT BRIDGE
    // ==========================================================

    property var assistantBridge: null


    // ==========================================================
    // SIGNALS
    // ==========================================================

    signal messageSent(string message)

    signal clearRequested()

    signal streamingStarted()

    signal streamingFinished()


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
    // STREAMING STATE
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
    // FOCUS WINDOW
    // ==========================================================

    Window {

        id: focusWindow

        visible: false

        width: 1100

        height: 720

        minimumWidth: 800

        minimumHeight: 500

        title:
            "KRAKKEN — Focus Mode"


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
    // BRIDGE PROPERTY DEBUG
    // ==========================================================

    onAssistantBridgeChanged: {

        console.log(
            "CHATVIEW: AssistantBridge changed:",
            root.assistantBridge
        )


        if (!root.assistantBridge) {

            console.error(
                "CHATVIEW: AssistantBridge is NULL."
            )

        } else {

            console.log(
                "CHATVIEW: AssistantBridge connected."
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

                            text:
                                "KRAKKEN"


                            color:
                                Theme.textPrimary


                            font.pixelSize:
                                root.fullscreen
                                ? 15
                                : 13


                            font.bold: true


                            font.letterSpacing:
                                2.2
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


                                if (
                                    root.assistantBridge
                                ) {

                                    root.assistantBridge
                                        .clearConversation()
                                }
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
        }
    }


    // ==========================================================
    // PUBLIC MESSAGE API
    // ==========================================================

    // IMPORTANT:
    //
    // ChatView ONLY displays the user message.
    //
    // It does NOT call AssistantBridge.sendMessage().
    //
    // Main.qml is responsible for sending commands.

    function addUserMessage(text) {

        if (
            !text ||
            text.trim().length === 0
        ) {
            return
        }


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


    // ==========================================================
    // ASSISTANT MESSAGE
    // ==========================================================

    function addAssistantMessage(text) {

        if (
            !text ||
            text.trim().length === 0
        ) {
            return
        }


        messageModel.append({

            role: "assistant",

            message: text,

            timestamp: currentTime(),

            streaming: false
        })


        trimMessages()

        scrollToBottom()
    }


    // ==========================================================
    // GENERIC MESSAGE
    // ==========================================================

    function addMessage(role, text) {

        if (
            !text ||
            text.trim().length === 0
        ) {
            return
        }


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

        // Prevent duplicate response-start events.

        if (root.streaming) {

            console.warn(
                "CHATVIEW: Duplicate responseStarted ignored."
            )

            return
        }


        messageModel.append({

            role: "assistant",

            message: "",

            timestamp: currentTime(),

            streaming: true
        })


        root.streamingIndex =
            messageModel.count - 1


        root.streaming = true


        root.state =
            "speaking"


        root.streamingStarted()


        scrollToBottom()
    }


    // ==========================================================
    // APPEND STREAM CHUNK
    // ==========================================================

    function appendStreamText(text) {

        if (!root.streaming) {
            return
        }


        if (
            root.streamingIndex < 0 ||
            root.streamingIndex >= messageModel.count
        ) {
            return
        }


        if (
            !text ||
            text.length === 0
        ) {
            return
        }


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


    // ==========================================================
    // FINISH STREAMING
    // ==========================================================

    function finishStreaming() {

        if (!root.streaming) {

            console.warn(
                "CHATVIEW: Duplicate responseFinished ignored."
            )

            return
        }


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


    // ==========================================================
    // CANCEL STREAMING
    // ==========================================================

    function cancelStreaming() {

        if (!root.streaming) {
            return
        }


        if (
            root.streamingIndex >= 0 &&
            root.streamingIndex < messageModel.count
        ) {

            var currentMessage =
                messageModel.get(
                    root.streamingIndex
                ).message


            if (
                !currentMessage ||
                currentMessage.length === 0
            ) {

                messageModel.remove(
                    root.streamingIndex
                )

            } else {

                messageModel.setProperty(
                    root.streamingIndex,
                    "streaming",
                    false
                )
            }
        }


        root.streaming = false

        root.streamingIndex = -1
    }


    // ==========================================================
    // FOCUS MODE
    // ==========================================================

    function enterFullscreen() {

        if (root.fullscreen) {
            return
        }


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


    // ==========================================================
    // EXIT FOCUS MODE
    // ==========================================================

    function exitFullscreen() {

        if (!root.fullscreen) {
            return
        }


        panel.parent =
            root


        panel.anchors.fill =
            root


        panel.anchors.margins = 0


        root.fullscreen = false


        focusWindow.hide()


        scrollToBottom()
    }


    // ==========================================================
    // TOGGLE FOCUS MODE
    // ==========================================================

    function toggleFullscreen() {

        if (root.fullscreen) {

            root.exitFullscreen()

        } else {

            root.enterFullscreen()
        }
    }


    // ==========================================================
    // SCROLL
    // ==========================================================

    function scrollToBottom() {

        if (!root.autoScroll) {
            return
        }


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


    // ==========================================================
    // CLEAR MESSAGES
    // ==========================================================

    function clearMessages() {

        messageModel.clear()

        root.streaming = false

        root.streamingIndex = -1

        root.state = "idle"
    }


    // ==========================================================
    // TRIM
    // ==========================================================

    function trimMessages() {

        while (
            messageModel.count >
            root.maxMessages
        ) {

            messageModel.remove(0)
        }
    }


    // ==========================================================
    // TIME
    // ==========================================================

    function currentTime() {

        var date =
            new Date()


        return Qt.formatTime(
            date,
            "hh:mm:ss"
        )
    }


    // ==========================================================
    // STATE DESCRIPTION
    // ==========================================================

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


        if (
            root.assistantBridge
        ) {

            console.log(
                "CHATVIEW: AssistantBridge connected successfully."
            )

        } else {

            console.error(
                "CHATVIEW: AssistantBridge was NOT connected."
            )
        }


        addAssistantMessage(
            "Krakken AI initialized. Awaiting your command."
        )
    }
}