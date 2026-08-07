import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Kraken

Rectangle {

    id: root

    color: Theme.surface

    border.color: Theme.border
    border.width: 1

    implicitHeight: Theme.topBarHeight

    RowLayout {

        anchors.fill: parent

        anchors.leftMargin: Theme.spacingXL
        anchors.rightMargin: Theme.spacingXL

        spacing: Theme.spacingL

        Text {

            text: Theme.appName

            color: Theme.textPrimary

            font.pixelSize: Theme.fontTitle
            font.bold: true
        }

        Item {
            Layout.fillWidth: true
        }

        Rectangle {

            width: 12
            height: 12

            radius: 6

            color: Theme.accentGreen

            SequentialAnimation on opacity {

                loops: Animation.Infinite

                NumberAnimation {
                    from: 1.0
                    to: 0.35
                    duration: 900
                }

                NumberAnimation {
                    from: 0.35
                    to: 1.0
                    duration: 900
                }
            }
        }

        Text {

            text: "ONLINE"

            color: Theme.accentGreen

            font.pixelSize: Theme.fontBody

            font.bold: true
        }
    }
}