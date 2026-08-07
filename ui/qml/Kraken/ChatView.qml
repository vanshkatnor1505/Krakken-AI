
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

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
    // MAIN CHAT SURFACE
    // ==========================================================

    Rectangle {

        id: panel

        anchors.fill: parent

        radius: Theme.radiusLarge

        color: Qt.rgba(
            0.04,
            0.07,
            0.12,
            0.62
        )

        border.width: 1

        border.color: Qt.rgba(
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

            visible: root.showHeader

            anchors.top: parent.top

            anchors.left: parent.left

            anchors.right: parent.right

            height: 58

            color: "transparent"

            RowLayout {

                anchors.fill: parent

                anchors.leftMargin: 24

                anchors.rightMargin: 18

                spacing: 11

                Rectangle {

                    Layout.alignment: Qt.AlignVCenter

                    width: 7

                    height: 7

                    radius: 3.5

                    color: root.stateColor

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

                        color: Theme.textPrimary

                        font.pixelSize: 13

                        font.bold: true

                        font.letterSpacing: 2.2
                    }

                    Text {

                        text: stateDescription()

                        color: root.stateColor

                        font.pixelSize: 8

                        font.bold: true

                        font.letterSpacing: 1.6

                        opacity: 0.72
                    }
                }

                Text {

                    Layout.alignment: Qt.AlignVCenter

                    text:
                        messageModel.count
                        + " MESSAGES"

                    color: Theme.textSecondary

                    font.pixelSize: 8

                    font.letterSpacing: 1

                    opacity: 0.55
                }

                Rectangle {

                    Layout.alignment: Qt.AlignVCenter

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

                    Behavior on color {

                        ColorAnimation {

                            duration: Theme.fast
                        }
                    }

                    Text {

                        anchors.centerIn: parent

                        text: "×"

                        color: Theme.textSecondary

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

                            messageModel.clear()

                            root.clearRequested()
                        }
                    }
                }
            }

            Rectangle {

                anchors.left: parent.left

                anchors.right: parent.right

                anchors.bottom: parent.bottom

                height: 1

                color: Qt.rgba(
                    1,
                    1,
                    1,
                    0.035
                )
            }
        }

        // ======================================================
        // MESSAGE STREAM
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

            anchors.leftMargin: 22

            anchors.rightMargin: 18

            anchors.topMargin: 14

            anchors.bottomMargin: 16

            clip: true

            model: messageModel

            spacing: 18

            boundsBehavior:
                Flickable.StopAtBounds

            ScrollBar.vertical: ScrollBar {

                policy: ScrollBar.AsNeeded
            }

            Text {

                anchors.centerIn: parent

                visible:
                    messageModel.count === 0

                text: "AWAITING COMMAND"

                color: Theme.textSecondary

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

                width: messageList.width

                height:
                    messageContent.height + 12

                property bool isUser:
                    role === "user"

                property color accent:
                    isUser
                    ? Theme.accent
                    : root.stateColor

                property real maximumBubbleWidth:
                    messageList.width * 0.82

                opacity: 0

                transform: Translate {

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
                            maximumBubbleWidth,
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

                            text: timestamp

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
                                maximumBubbleWidth,
                                messageText.implicitWidth + 30
                            )

                        height:
                            messageText.implicitHeight + 22

                        anchors.right:
                            messageDelegate.isUser
                            ? parent.right
                            : undefined

                        radius: 13

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

                            anchors.leftMargin: 15

                            anchors.rightMargin: 15

                            anchors.topMargin: 11

                            anchors.bottomMargin: 11

                            text: message

                            color: Theme.textPrimary

                            font.pixelSize: 13

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

                            delegate: Rectangle {

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

            // ==================================================
            // AUTO SCROLL
            // ==================================================

            onCountChanged: {

                if (!root.autoScroll)
                    return

                Qt.callLater(function() {

                    messageList.positionViewAtEnd()
                })
            }
        }
    }

    // ==========================================================
    // PUBLIC MESSAGE API
    // ==========================================================

    function addUserMessage(text) {

        if (!text || text.trim().length === 0)
            return

        messageModel.append({

            role: "user",

            message: text.trim(),

            timestamp: currentTime()
        })

        trimMessages()

        root.messageSent(text.trim())
    }

    function addAssistantMessage(text) {

        if (!text || text.trim().length === 0)
            return

        messageModel.append({

            role: "assistant",

            message: text,

            timestamp: currentTime()
        })

        trimMessages()
    }

    function addMessage(role, text) {

        if (!text || text.trim().length === 0)
            return

        messageModel.append({

            role: role,

            message: text,

            timestamp: currentTime()
        })

        trimMessages()
    }

    // ==========================================================
    // STREAMING API
    // ==========================================================

    function startStreaming() {

        if (root.streaming)
            finishStreaming()

        messageModel.append({

            role: "assistant",

            message: "",

            timestamp: currentTime(),

            streaming: true
        })

        root.streamingIndex =
            messageModel.count - 1

        root.streaming = true

        root.streamingStarted()

        root.state = "speaking"

        scrollToBottom()
    }

    function appendStreamText(text) {

        if (!root.streaming)
            return

        if (
            root.streamingIndex < 0 ||
            root.streamingIndex >= messageModel.count
        ) {
            return
        }

        var current =
            messageModel.get(
                root.streamingIndex
            ).message

        messageModel.setProperty(
            root.streamingIndex,
            "message",
            current + text
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
    // UTILITIES
    // ==========================================================

    function scrollToBottom() {

        if (!root.autoScroll)
            return

        Qt.callLater(function() {

            messageList.positionViewAtEnd()
        })
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

        var date = new Date()

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
    // INITIAL MESSAGE
    // ==========================================================

    Component.onCompleted: {

        addAssistantMessage(
            "Krakken AI initialized. Awaiting your command."
        )
    }
}

