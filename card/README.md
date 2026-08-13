# Upcoming Media Card (BetaSeries Fork)

A fork of the [Upcoming Media Card](https://github.com/custom-cards/upcoming-media-card) by [Custom Cards for Home Assistant](https://github.com/custom-cards) and contributors.

## What's different in this fork

This fork adds functionality specific to the [BetaSeries Home Assistant integration](../):

- **Mark episodes as watched**: Click the eye icon to instantly mark an episode as watched in your BetaSeries account.
- **Unbounded display**: Remove the viewport height restriction that limited card content. Display as many rows as needed without being capped by screen size.
- **Responsive columns**: Configurable number of columns with automatic overflow handling.
- **BetaSeries device selector**: Link the card to your BetaSeries integration for watched button functionality.
- **Multiple button styles**: Choose from dark, ring, or light themed watched buttons to match your Lovelace design.
- **Live search**: Optional search bar to filter displayed items in real time by show title or streaming platform.

## Configuration

### Basic example

```yaml
type: custom:upcoming-media-card
entity: sensor.betaseries_shows_to_catch_up_on
config_entry: abc123def456  # Your BetaSeries integration
watched_button_style: dark
overflow_fit: content
```

### Options

Below are the options specific to this BetaSeries fork. For a complete list of all available options from the original project, refer to the [upstream repository documentation](https://github.com/custom-cards/upcoming-media-card#options).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `entity` | string | - | Entity ID to display |
| `config_entry` | string | - | BetaSeries integration config entry ID (enables watched button) |
| `watched_button_style` | select | `dark` | Button appearance: `dark`, `ring`, or `light` |
| `overflow_fit` | select | `viewport` | Layout mode: `viewport` (limited to screen) or `content` (full height) |
| `max_columns` | number | 3 | Maximum number of columns before wrapping |
| `title` | string | - | Card title |
| `enable_search` | boolean | `false` | Show a live search bar to filter items by title or streaming platform |

## Credits

This fork is based on the excellent [Upcoming Media Card](https://github.com/custom-cards/upcoming-media-card) project by [Custom Cards for Home Assistant](https://github.com/custom-cards). Thank you to all contributors for creating and maintaining this flexible card component.

The original card provides the foundation for displaying upcoming media events in Home Assistant with a responsive, customizable layout. This fork extends it with BetaSeries-specific integrations while maintaining compatibility with the original design philosophy.

## License

This fork maintains the same [MIT License](https://github.com/custom-cards/upcoming-media-card/blob/master/LICENSE) as the original Upcoming Media Card project.
