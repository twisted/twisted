/*
Have a single comment on a PR, identified by a comment marker.

Create a new comment if no comment already exists.
Update the content of the existing comment.


https://octokit.github.io/rest.js/v19
*/
module.exports = async ({github, context, process}) => {
    var octokit_rest = github
    if (context.eventName != "pull_request") {
        // Only PR are supported.
        return
    }

    var sleep = function(second) {
        return new Promise(resolve => setTimeout(resolve, second * 1000))
    }

    /*
    Perform the actual logic.

    This is wrapped so that we can retry on errors.
    */
    var doAction = async function() {

        console.log(context)

        fs = require('fs');

        const body = fs.readFileSync(
            process.env.GITHUB_WORKSPACE + "/" + process.env.COMMENT_BODY, 'utf8');
        var comment_id = null
        var comment_marker = '\n' + process.env.COMMENT_MARKER
        var comment_body = body + comment_marker

        var comments = await octokit_rest.issues.listComments({
            owner: context.repo.owner,
            repo: context.repo.repo,
            issue_number: context.payload.number,
          })

        console.log(comments)

        comments.data.forEach(comment => {
            if (comment.body.endsWith(comment_marker)) {
                comment_id = comment.id
            }
        })

        if (comment_id) {
            // We have an existing comment.
            // update the content.
            await octokit_rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: comment_id,
                body: comment_body,
            })
            return
        }

        // Create a new comment.
        await octokit_rest.issues.createComment({
            owner: context.repo.owner,
            repo: context.repo.repo,
            issue_number: context.payload.number,
            body: comment_body,
        })

    }

    try {
        await doAction()
    } catch (e) {
        await sleep(5)
        await doAction()
    }
}
